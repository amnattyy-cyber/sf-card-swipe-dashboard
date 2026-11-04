"""Build index.html for the SF+ card swipe dashboard.

Inputs (folder data/):
  - Format_SF*.xlsx            : one sheet per week (WKxx); columns A-H shop master,
                                 I-O daily swipe counts (Mon-Sun), P days swiped, Q flag
  - Report_Sell_Out_SF*.csv    : optional, sell out per IMEI (used in CSV export)
  - Report_Sales_Funnel*.csv   : optional, attempt / offer_seen / purchase (used in CSV export)
Weeks already built are kept in history/weeks_history.json so older weeks stay
on the dashboard even after they are removed from the Excel file.
"""
import glob, json, os, re, subprocess, sys
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
HIST = os.path.join(ROOT, 'history', 'weeks_history.json')
TEMPLATE = os.path.join(ROOT, 'scripts', 'template.html')
OUT = os.path.join(ROOT, 'index.html')
MAX_WEEKS = 6  # number of week tabs shown


def _norm(name):
    return re.sub(r'[^a-z0-9]', '', name.lower())


def _commit_time(path):
    """Last git commit time of a file (uploads all share one mtime in Actions)."""
    try:
        out = subprocess.run(['git', 'log', '-1', '--format=%ct', '--', path], cwd=ROOT,
                             capture_output=True, text=True).stdout.strip()
        return int(out) if out else int(os.path.getmtime(path))
    except Exception:
        return int(os.path.getmtime(path))


def find(kind):
    """Files in data/ of one kind, oldest first.  Names are matched loosely, so
    'Format SF+.xlsx', 'Format_SF.xlsx', 'Report Sell Out SF+_...csv' all work."""
    rules = {
        'format': lambda n: n.endswith('xlsx') and 'format' in n and 'sf' in n,
        'sellout': lambda n: n.endswith('csv') and 'sellout' in n,
        'funnel': lambda n: n.endswith('csv') and 'funnel' in n,
    }
    files = [f for f in glob.glob(os.path.join(DATA, '*')) if rules[kind](_norm(os.path.basename(f)))]
    return sorted(files, key=lambda f: (_commit_time(f), os.path.basename(f)))


def to_iso(v):
    return pd.to_datetime(v).strftime('%Y-%m-%d')


def read_format(path):
    weeks = {}
    xl = pd.read_excel(path, sheet_name=None, header=0)
    for name, df in xl.items():
        key = name.strip().upper().replace(' ', '')
        if not re.fullmatch(r'WK\d+', key):
            continue
        df = df.dropna(subset=[df.columns[0]])
        dates = [to_iso(c) for c in df.columns[8:15]]
        avail = [d for i, d in enumerate(dates) if df.iloc[:, 8 + i].notna().any()]
        recs = []
        for _, r in df.iterrows():
            try:
                code = int(r.iloc[0])
            except (TypeError, ValueError):
                continue
            days = {d: int(r.iloc[8 + i]) for i, d in enumerate(dates) if d in avail and pd.notna(r.iloc[8 + i])}
            for d in avail:
                days.setdefault(d, 0)
            n_days = sum(1 for v in days.values() if v > 0)
            flag = r.iloc[16] if pd.notna(r.iloc[16]) else ('Pass' if n_days >= 2 else 'Not Pass')
            tds = r.iloc[1]
            recs.append(dict(shop_code=code, code_tds=int(tds) if pd.notna(tds) else '', shop_name=str(r.iloc[2]),
                             type_shop=str(r.iloc[3]), area=str(r.iloc[4]), size_shop=str(r.iloc[5]),
                             region=str(r.iloc[6]), focus_sf=str(r.iloc[7]), days_swiped=n_days,
                             flag=str(flag).strip(), days=days))
        weeks[key] = dict(key=key, dates=dates, available_dates=avail, records=recs)
    return weeks


SELL_HIST = os.path.join(ROOT, 'history', 'sellout_daily.json')


def _model_labels(df, prefix_map):
    """Model name (series + capacity) and series for every row.  Rows without a
    DESCRIPTION get their series from other rows with the same Model Code prefix."""
    parts = df['DESCRIPTION'].fillna('').astype(str).str.split(',')
    fam = parts.str[2].fillna('').str.strip()
    cap = parts.str[4].fillna('').str.strip()
    pre = df['Model Code'].fillna('').astype(str).str[:7]
    for p_, f_ in zip(pre[fam != ''], fam[fam != '']):
        prefix_map.setdefault(p_, f_)
    missing = fam == ''
    fam = fam.where(~missing, pre.map(prefix_map).fillna(df['Model Code'].fillna('ไม่ระบุรุ่น').astype(str)))
    model = (fam + ' ' + cap).str.strip().where(~missing, fam + ' (ไม่ระบุความจุ)')
    return model, fam


def read_sellout():
    """Sell out units per shop per day per model.  Raw CSVs (which contain IMEIs) are
    reduced to counts, merged into history/sellout_daily.json, and then deleted.
    History format: {"v": 2, "days": {date: {shop: {model: qty}}}, "family": {model: series},
                     "prefix": {model_code_prefix: series}}"""
    raw = json.load(open(SELL_HIST, encoding='utf-8')) if os.path.exists(SELL_HIST) else {}
    if raw.get('v') != 2:  # old format: {date: {shop: qty}}
        raw = {'v': 2, 'days': {d: {sc: {'ไม่ระบุรุ่น': q} for sc, q in shops.items()} for d, shops in raw.items()},
               'family': {'ไม่ระบุรุ่น': 'ไม่ระบุรุ่น'}, 'prefix': {}}
    files = find('sellout')
    if files:
        df = pd.concat([pd.read_csv(f, encoding='utf-8-sig', dtype={'Mobile_IMEI': str}) for f in files])
        # the report can list one device (IMEI) several times under different product codes
        df = df.dropna(subset=['Mobile_IMEI']).drop_duplicates(subset=['Mobile_IMEI'], keep='last')
        df['d'] = pd.to_datetime(df['Financed_Date'], format='%m/%d/%Y').dt.strftime('%Y-%m-%d')
        df['model'], df['family'] = _model_labels(df, raw['prefix'])
        new = {}
        for (sc, d, mo), q in df.groupby(['Partner Code', 'd', 'model'])['QTY SF+'].sum().items():
            new.setdefault(d, {}).setdefault(str(int(sc)), {})[mo] = int(q)
        raw['days'].update(new)  # dates in the new file replace older counts for those dates
        raw['family'].update(dict(zip(df['model'], df['family'])))
        json.dump(raw, open(SELL_HIST, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'), sort_keys=True)
        for f in files:
            os.remove(f)
    days = raw['days']
    if not days:
        return {}, (None, None), None
    sell = {}
    for d, shops in days.items():
        for sc, models in shops.items():
            sell[(int(sc), d)] = sum(models.values())
    return sell, (min(days), max(days)), raw


def sellout_payload(raw, master):
    """Compact model-level rows for the 'Sell Out by Model' tab (master shops only)."""
    if not raw:
        return {'models': [], 'family': [], 'rows': [], 'range': [None, None]}
    models = sorted({mo for shops in raw['days'].values() for ms in shops.values() for mo in ms})
    idx = {m: i for i, m in enumerate(models)}
    rows = [[d, int(sc), idx[mo], q] for d, shops in sorted(raw['days'].items())
            for sc, ms in shops.items() if int(sc) in master for mo, q in ms.items()]
    return {'models': models, 'family': [raw['family'].get(m, m) for m in models], 'rows': rows,
            'range': [min(raw['days']), max(raw['days'])]}


def read_funnel():
    files = find('funnel')
    if not files:
        return {}, set()
    parts = []
    for i, f in enumerate(files):
        t = pd.read_csv(f); t['_order'] = i; parts.append(t)
    df = pd.concat(parts)
    df['d'] = pd.to_datetime(df['Date'], format='%m/%d/%Y').dt.strftime('%Y-%m-%d')
    # a newer file replaces older rows for the same date
    newest = df.groupby('d')['_order'].transform('max')
    df = df[df['_order'] == newest]
    g = df.groupby(['Shop Code', 'd'])[['Attempt', 'offer_seen', 'purchase_completed']].sum()
    return {(int(k[0]), k[1]): tuple(int(x) for x in v) for k, v in g.iterrows()}, set(df.d)

THAI_MONTHS = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.']
PASS_DAYS = 2


def thd(iso):
    y, m, d = map(int, iso.split('-'))
    return f'{d} {THAI_MONTHS[m - 1]}'


def date_span(dates):
    """'2-3 พ.ย.' for consecutive dates in one month, otherwise a comma list."""
    if not dates:
        return ''
    days = [int(d[8:]) for d in dates]; months = {d[5:7] for d in dates}
    if len(months) == 1 and days == list(range(days[0], days[0] + len(days))):
        m = THAI_MONTHS[int(dates[0][5:7]) - 1]
        return f'{days[0]} {m}' if len(days) == 1 else f'{days[0]}-{days[-1]} {m}'
    return ', '.join(thd(d) for d in dates)


def short_name(n):
    return re.sub(r'^True Shop\s+', '', str(n)).strip()


def build_sms(w, region=None):
    R = [r for r in w['records'] if r['focus_sf'] == 'Y' and (region is None or r['region'] == region)]; avail = w['available_dates']; n_left = len(w['dates']) - len(avail)
    passed = [r for r in R if r['flag'] == 'Pass']
    crit = [r for r in R if r['focus_sf'] == 'Y' and r['days_swiped'] == 0]
    crit_codes = {r['shop_code'] for r in crit}
    notpass = [r for r in R if r['flag'] != 'Pass' and r['shop_code'] not in crit_codes]
    L = ['Dashboard Analysis: การเสียบบัตร SF+' + (f' · {region}' if region else ''),
         f"· สัปดาห์ {w['key']} ({thd(w['dates'][0])}–{thd(w['dates'][-1])} {w['dates'][-1][:4]})"]
    if len(avail) == len(w['dates']):
        L.append(f'มีข้อมูลการเสียบบัตรครบทั้ง {len(avail)} วัน (ผลสรุปสัปดาห์)')
    else:
        L.append(f'มีข้อมูลการเสียบบัตรเฉพาะวันที่ {date_span(avail)} (เหลืออีก {n_left} วันในสัปดาห์)')
    L.append(f'เฉพาะร้าน Focus SF+ (Y) · ผ่านเกณฑ์แล้ว {len(passed)}/{len(R)} สาขา ({len(passed) / max(len(R), 1) * 100:.1f}%) · เกณฑ์ผ่าน = เสียบบัตร {PASS_DAYS} วัน/week ขึ้นไป')

    def by_area(rows):
        out = []
        groups = {}
        for r in rows:
            groups.setdefault((r['region'], r['area']), []).append(r)
        for (_, area), rs in sorted(groups.items()):
            out.append(f'[{area}] {len(rs)} สาขา')
            yield out, rs
            out.clear()

    L += ['', f'⚠ รายชื่อร้าน Focus SF+ ที่มีความเสี่ยงสูง (ยังไม่เสียบบัตรเลย) {len(crit)} สาขา',
          f'เสียบแล้ว 0 วัน · ต้องเสียบเพิ่ม {PASS_DAYS} วัน']
    if not crit:
        L.append('✓ ไม่มี')
    for head, rs in by_area(crit):
        L += head + [f'- {short_name(r["shop_name"])}' for r in sorted(rs, key=lambda r: short_name(r['shop_name']))]

    L += ['', f'⚠ ร้าน Focus SF+ ที่ยังไม่ผ่านเกณฑ์ (Not Pass) ในสัปดาห์นี้ {len(notpass)} สาขา (ไม่รวมกลุ่มด้านบน)']
    if not notpass:
        L.append('✓ ไม่มี')
    for head, rs in by_area(notpass):
        L += head
        for r in sorted(rs, key=lambda r: (-r['days_swiped'], short_name(r['shop_name']))):
            need = max(PASS_DAYS - r['days_swiped'], 0)
            L.append(f'- {short_name(r["shop_name"])}: เสียบ {r["days_swiped"]} วัน ต้องเสียบเพิ่ม {need} วัน')
    return '\n'.join(L)


def write_sms(w):
    import html as _h
    msgs = [('ทั้งประเทศ', 'sms.txt', build_sms(w)), ('เฉพาะ BMA', 'sms_bma.txt', build_sms(w, 'BMA'))]
    blocks = []
    for i, (title, fname, text) in enumerate(msgs):
        open(os.path.join(ROOT, fname), 'w', encoding='utf-8').write(text)
        blocks.append(f'<section><div class="bar"><h2>{title}</h2><button class="primary copy" data-t="m{i}">📋 คัดลอกข้อความ</button>'
                      f'<span class="ok"></span></div><pre id="m{i}">{_h.escape(text)}</pre></section>')
    page = open(os.path.join(ROOT, 'scripts', 'sms_template.html'), encoding='utf-8').read()
    open(os.path.join(ROOT, 'sms.html'), 'w', encoding='utf-8').write(
        page.replace('__BLOCKS__', '\n'.join(blocks)).replace('__WEEK__', w['key']))


def main():
    fmt_files = find('format')
    if not fmt_files:
        sys.exit('ไม่พบไฟล์ Format SF (.xlsx) ในโฟลเดอร์ data/')
    fmt_path = fmt_files[-1]
    weeks = json.load(open(HIST, encoding='utf-8')) if os.path.exists(HIST) else {}
    weeks.update(read_format(fmt_path))

    num = lambda k: int(k[2:])
    with_data = sorted([k for k, w in weeks.items() if w['available_dates']], key=num)
    if not with_data:
        sys.exit('ยังไม่มีสัปดาห์ที่มีข้อมูล')
    last = num(with_data[-1])
    keys = sorted([k for k in weeks if num(k) <= last], key=num)[-MAX_WEEKS:]

    # master = shops of the latest week; drop shops not in master
    master = {r['shop_code'] for r in weeks[with_data[-1]]['records']}
    sell, (smin, smax), sell_raw = read_sellout()
    fun, fdates = read_funnel()

    out = []
    for k in keys:
        w = weeks[k]
        w['records'] = [r for r in w['records'] if r['shop_code'] in master]
        w['sell_dates'] = [d for d in w['dates'] if smin and smin <= d <= smax]
        w['funnel_dates'] = [d for d in w['dates'] if d in fdates]
        for r in w['records']:
            sc = r['shop_code']
            r['sellout'] = sum(sell.get((sc, d), 0) for d in w['sell_dates'])
            t = [fun.get((sc, d), (0, 0, 0)) for d in w['funnel_dates']]
            r['f_att'] = sum(a[0] for a in t); r['f_offer'] = sum(a[1] for a in t); r['f_buy'] = sum(a[2] for a in t)
        out.append(w)

    html = open(TEMPLATE, encoding='utf-8').read()
    html = html.replace('/*__WEEKS__*/', json.dumps(out, ensure_ascii=False, separators=(',', ':')))
    html = html.replace('/*__SELLOUT__*/', json.dumps(sellout_payload(sell_raw, master), ensure_ascii=False, separators=(',', ':')))
    open(OUT, 'w', encoding='utf-8').write(html)

    # keep every week that has data for future builds
    hist = {k: w for k, w in weeks.items() if w['available_dates']}
    os.makedirs(os.path.dirname(HIST), exist_ok=True)
    json.dump(hist, open(HIST, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

    latest_week = [w for w in out if w['available_dates']][-1]
    write_sms(latest_week)

    # keep only the newest Format file so the next upload is unambiguous
    for f in fmt_files[:-1]:
        os.remove(f)

    print('source:', os.path.basename(fmt_path))
    for w in out:
        print(f"{w['key']}: {len(w['available_dates'])}/7 วัน, {len(w['records'])} สาขา, "
              f"Pass {sum(r['flag'] == 'Pass' for r in w['records'])}")


if __name__ == '__main__':
    main()
