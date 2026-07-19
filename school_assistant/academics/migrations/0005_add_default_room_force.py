# academics/migrations/0005_add_default_room_force.py
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0004_classsection_teacher_incharge'),  # ✅ APNI AKHRI MIGRATION (0004)
    ]

    operations = [
        migrations.AddField(
            model_name='classsection',
            name='default_room',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='academics.room',
            ),
        ),
    ]