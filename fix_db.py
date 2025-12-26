from app import app, db
from sqlalchemy import text

with app.app_context():
    with db.engine.connect() as conn:
        trans = conn.begin()
        try:
            # 1. إصلاح جدول المنتجات (إضافة الضريبة)
            print("جاري التحقق من جدول المنتجات...")
            conn.execute(text("ALTER TABLE product ADD COLUMN IF NOT EXISTS tax FLOAT DEFAULT 0;"))
            print("✅ تم إضافة عمود 'tax' لجدول المنتجات.")

            # 2. إصلاح جدول المتاجر (إضافة نهاية الاشتراك)
            print("جاري التحقق من جدول المتاجر...")
            conn.execute(text("ALTER TABLE shop ADD COLUMN IF NOT EXISTS subscription_end TIMESTAMP;"))
            print("✅ تم إضافة عمود 'subscription_end' لجدول المتاجر.")

            trans.commit()
            print("\n🎉 تم تحديث قاعدة البيانات بنجاح!")
        except Exception as e:
            trans.rollback()
            print(f"\n❌ حدث خطأ (ربما الأعمدة موجودة بالفعل): {e}")

    # 3. التأكد من إنشاء الجداول الجديدة (مثل الاشتراكات)
    try:
        db.create_all()
        print("✅ تم إنشاء الجداول الجديدة (Subscription وغيرها).")
    except Exception as e:
        print(f"⚠️ ملاحظة عند إنشاء الجداول: {e}")