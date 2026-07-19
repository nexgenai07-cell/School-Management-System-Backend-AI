# academics/migrations/0006_add_teacher_incharge_force.py
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0005_add_default_room_force'),  # ✅ APNI NAYI AKHRI MIGRATION
        # Note: 0005 is the one we just added, so we depend on that.
    ]

    operations = [
        migrations.AddField(
            model_name='classsection',
            name='teacher_incharge',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='accounts.teacherprofile',  # model name as per your app
            ),
        ),
    ]