from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='chatsession',
            name='bot_type',
            field=models.CharField(
                choices=[
                    ('maintenance', 'Maintenance & Help Desk Bot'),
                    ('fee', 'Fee Bot'),
                    ('media', 'Media Bot'),
                    ('assignment', 'Assignment Bot'),
                    ('exam', 'Exam Bot'),
                    ('attendance', 'Attendance & Compliance Bot'),
                    ('certificate', 'Certificates Bot'),
                    ('scholarship', 'Scholarship Bot'),
                    ('inventory', 'Inventory Bot'),
                    ('event', 'Event Bot'),
                    ('users', 'User Approval Bot'),
                    ('general', 'General Assistant'),
                ],
                default='general',
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name='PendingAction',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bot_type', models.CharField(max_length=20)),
                ('action_name', models.CharField(max_length=50)),
                ('params', models.JSONField(default=dict)),
                ('summary', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('session', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='pending_action', to='chat.chatsession')),
            ],
        ),
    ]