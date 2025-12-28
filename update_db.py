from app import app, db
from sqlalchemy import text

with app.app_context():
    try:
        # 1. إضافة العمود الناقص لجدول المتاجر
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE shop ADD COLUMN subscription_end TIMESTAMP;"))
            conn.commit()
        print("✅ تم إضافة عمود subscription_end بنجاح!")
    except Exception as e:
        print(f"⚠️ ملاحظة: {e}")

    # 2. إنشاء جدول الاشتراكات الجديد (Subscription)
    db.create_all()
    print("✅ تم تحديث الجداول وإنشاء جدول الاشتراكات.")