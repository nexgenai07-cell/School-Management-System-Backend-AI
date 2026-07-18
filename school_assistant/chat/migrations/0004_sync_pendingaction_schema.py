from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('chat', '0003_remove_chatsession_bot_type_alter_pendingaction_id'),
    ]

    operations = [
        migrations.RemoveField(model_name='pendingaction', name='action_name'),
        migrations.RemoveField(model_name='pendingaction', name='summary'),
        migrations.AddField(
            model_name='pendingaction',
            name='tool_name',
            field=models.CharField(max_length=100, default=''),
        ),
        migrations.AddField(
            model_name='pendingaction',
            name='status',
            field=models.CharField(max_length=20, default='pending'),
        ),
        migrations.AddField(
            model_name='pendingaction',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]