# Dashboard การเสียบบัตร SF+

ดู dashboard: https://amnattyy-cyber.github.io/sf-card-swipe-dashboard/

## อัปเดตข้อมูลประจำวัน

1. เปิดโฟลเดอร์ [`data/`](data) แล้วกด **Add file → Upload files**
2. ลากไฟล์ใส่ แล้วกด **Commit changes**
   - `Format_SF.xlsx` (จำเป็น) ใช้ชื่อเดิมเพื่อทับไฟล์เก่า และเพิ่มชีตสัปดาห์ใหม่ เช่น `WK46` ได้เลย
   - `Report_Sell_Out_SF_*.csv` และ `Report_Sales_Funnel_*.csv` (ไม่บังคับ) ใช้ในไฟล์ Export CSV เท่านั้น
3. รอ 1–2 นาที ดูสถานะได้ที่แท็บ **Actions** เมื่อขึ้นเครื่องหมาย ✓ สีเขียว ให้รีเฟรชหน้า dashboard

## หลักการทำงาน

- Dashboard ใช้ชีต `WKxx` ใน Format_SF.xlsx โดยสัปดาห์ล่าสุดคือสัปดาห์สุดท้ายที่มีข้อมูล และแสดงย้อนหลัง 6 สัปดาห์
- สัปดาห์ที่เคยสร้างแล้วจะถูกเก็บไว้ใน `history/weeks_history.json` ลบชีตเก่าออกจาก Excel ได้โดยข้อมูลไม่หาย
- แสดงเฉพาะร้านใน Master ของสัปดาห์ล่าสุด
- ไฟล์ Sell Out / Funnel อัปโหลดสะสมไว้หลายไฟล์ได้ ระบบตัดรายการซ้ำให้ (Sell Out ใช้ IMEI ส่วน Funnel ใช้วันที่จากไฟล์ใหม่สุด)
- ถ้า Actions ขึ้นสีแดง ให้เปิดดูข้อความ error มักเกิดจากรูปแบบคอลัมน์ในไฟล์เปลี่ยน
