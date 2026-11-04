"""Build index.html for the SF+ card swipe dashboard.

Inputs (folder data/):
  - Format_SF*.xlsx            : one sheet per week (WKxx); columns A-H shop master,
                                 I-O daily swipe counts (Mon-Sun), P days swiped, Q flag
  - Report_Sell_Out_SF*.csv    : optional, sell out per IMEI (used in CSV export)
  - Report_Sales_Funnel*.csv   : optional, attempt / offer_seen / purchase (used in CSV export)
Weeks already built are kept in history/weeks_history.json so older weeks stay
on the dashboard even after they are removed from the Excel file.
"""
import glob, json, os, re, sys
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
HIST = os.path.join(ROOT, 'history', 'weeks_history.json')
TEMPLATE = os.path.join(ROOT, 'scripts', 'template.html')
OUT = os.path.join(ROOT, 'index.html')
MAX_WEEKS = 6  # number of week tabs shown


def latest(pattern):
    files = sorted(glob.glob(os.path.join(DATA, pattern)))  # by name (dates in filenames)
    return files


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


def read_sellout():
    """Sell out units per shop per day.  Raw CSVs (which contain IMEIs) are reduced to
    shop/day counts, merged into history/sellout_daily.json, and then deleted."""
    hist = json.load(open(SELL_HIST, encoding='utf-8')) if os.path.exists(SELL_HIST) else {}
    files = latest('Report_Sell_Out*.csv')
    if files:
        df = pd.concat([pd.read_csv(f, encoding='utf-8-sig', dtype={'Mobile_IMEI': str}) for f in files])
        # the report can list one device (IMEI) several times under different product codes
        df = df.dropna(subset=['Mobile_IMEI']).drop_duplicates(subset=['Mobile_IMEI'], keep='last')
        df['d'] = pd.to_datetime(df['Financed_Date'], format='%m/%d/%Y').dt.strftime('%Y-%m-%d')
        new = {}
        for (sc, d), q in df.groupby(['Partner Code', 'd'])['QTY SF+'].sum().items():
            new.setdefault(d, {})[str(int(sc))] = int(q)
        hist.update(new)  # dates in the new file replace older counts for those dates
        json.dump(hist, open(SELL_HIST, 'w', encoding='utf-8'), separators=(',', ':'), sort_keys=True)
        for f in files:
            os.remove(f)
    if not hist:
        return {}, (None, None)
    sell = {(int(sc), d): q for d, shops in hist.items() for sc, q in shops.items()}
    return sell, (min(hist), max(hist))


def read_funnel():
    files = latest('Report_Sales_Funnel*.csv')
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


def main():
    fmt_files = latest('Format*SF*.xlsx')
    if not fmt_files:
        sys.exit('ไม่พบไฟล์ Format_SF*.xlsx ในโฟลเดอร์ data/')
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
    sell, (smin, smax) = read_sellout()
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
    open(OUT, 'w', encoding='utf-8').write(html)

    # keep every week that has data for future builds
    hist = {k: w for k, w in weeks.items() if w['available_dates']}
    os.makedirs(os.path.dirname(HIST), exist_ok=True)
    json.dump(hist, open(HIST, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

    print('source:', os.path.basename(fmt_path))
    for w in out:
        print(f"{w['key']}: {len(w['available_dates'])}/7 วัน, {len(w['records'])} สาขา, "
              f"Pass {sum(r['flag'] == 'Pass' for r in w['records'])}")


if __name__ == '__main__':
    main()
