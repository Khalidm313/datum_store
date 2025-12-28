from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        # الاتصال بقاعدة البيانات
        with db.engine.connect() as conn:
            # إضافة عمود الشعار (logo_file) لجدول المتجر (shop)
            # IF NOT EXISTS تمنع حدوث خطأ إذا كان العمود موجوداً مسبقاً
            conn.execute(text("ALTER TABLE shop ADD COLUMN IF NOT EXISTS logo_file VARCHAR(150);"))
            conn.commit()
            
            print("--------------------------------------------------")
            print("✅ تم إضافة العمود logo_file بنجاح!")
            print("--------------------------------------------------")
    except Exception as e:
        print("--------------------------------------------------")
        print(f"❌ حدث خطأ: {e}")
        print("--------------------------------------------------")