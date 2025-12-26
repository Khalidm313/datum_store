from app import app, db
from sqlalchemy import text

with app.app_context():
    print("--- جاري فحص وإصلاح قاعدة البيانات ---")
    
    with db.engine.connect() as conn:
        # 1. محاولة إضافة عمود customer_phone
        try:
            conn.execute(text('ALTER TABLE invoice ADD COLUMN customer_phone VARCHAR(50);'))
            print("✅ تم إضافة عمود الهاتف (customer_phone).")
        except Exception as e:
            print("ℹ️ عمود الهاتف موجود مسبقاً.")

        # 2. محاولة إضافة عمود notes
        try:
            conn.execute(text('ALTER TABLE invoice ADD COLUMN notes VARCHAR(255);'))
            print("✅ تم إضافة عمود الملاحظات (notes).")
        except Exception as e:
            print("ℹ️ عمود الملاحظات موجود مسبقاً.")
            
        conn.commit()

    print("--- اكتملت العملية بنجاح! ---")