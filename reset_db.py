from app import app, db

with app.app_context():
    # حذف كل شيء قديم
    db.drop_all()
    print("تم حذف الجداول القديمة...")

    # إنشاء كل شيء جديد (بالتعديلات الجديدة)
    db.create_all()
    print("تم إنشاء قاعدة البيانات الجديدة بنجاح!")