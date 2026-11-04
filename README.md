# Dashboard การเสียบบัตร SF+

ดู dashboard: https://amnattyy-cyber.github.io/sf-card-swipe-dashboard/

## อัปเดตข้อมูลประจำวัน

1. เปิดโฟลเดอร์ [`data/`](data) แล้วกด **Add file → Upload files**
2. ลากไฟล์ใส่ แล้วกด **Commit changes**
   - ไฟล์ Format SF (จำเป็น) ชื่อไฟล์ต้องมีคำว่า Format และ SF เช่น `Format SF+.xlsx` ระบบใช้ไฟล์ที่อัปโหลดล่าสุดและลบไฟล์เก่าให้เอง
   - `Report_Sell_Out_SF_*.csv` และ `Report_Sales_Funnel_*.csv` (ไม่บังคับ) ใช้ในไฟล์ Export CSV เท่านั้น
3. รอ 1–2 นาที ดูสถานะได้ที่แท็บ **Actions** เมื่อขึ้นเครื่องหมาย ✓ สีเขียว ให้รีเฟรชหน้า dashboard

## สรุป SMS ประจำวัน

เปิด https://amnattyy-cyber.github.io/sf-card-swipe-dashboard/sms.html แล้วกด **📋 คัดลอกข้อความ** ระบบสร้างสรุปใหม่ทุกครั้งที่อัปโหลดไฟล์ Format SF (มีไฟล์ข้อความ `sms.txt` ให้ด้วย)

## หลักการทำงาน

- Dashboard ใช้ชีต `WKxx` ใน Format_SF.xlsx โดยสัปดาห์ล่าสุดคือสัปดาห์สุดท้ายที่มีข้อมูล และแสดงย้อนหลัง 6 สัปดาห์
- สัปดาห์ที่เคยสร้างแล้วจะถูกเก็บไว้ใน `history/weeks_history.json` ลบชีตเก่าออกจาก Excel ได้โดยข้อมูลไม่หาย
- แสดงเฉพาะร้านใน Master ของสัปดาห์ล่าสุด
- ไฟล์ Sell Out จะถูกย่อเป็นยอดต่อร้านต่อวันแล้วเก็บไว้ใน `history/sellout_daily.json` จากนั้นระบบจะลบไฟล์ CSV ทิ้ง เพื่อไม่ให้ IMEI ค้างอยู่ใน repo (IMEI ซ้ำนับเป็น 1 เครื่อง)
- ไฟล์ Funnel อัปโหลดสะสมไว้ได้ ถ้าวันที่ซ้ำกัน ระบบใช้ข้อมูลจากไฟล์ที่ชื่อใหม่สุด
- ถ้า Actions ขึ้นสีแดง ให้เปิดดูข้อความ error มักเกิดจากรูปแบบคอลัมน์ในไฟล์เปลี่ยน
