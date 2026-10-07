from django.db import migrations

def verify_existing_users(apps, schema_editor):
    CustomUser = apps.get_model('users', 'CustomUser')
    # Mark existing test profiles as phone verified so they are never blocked
    CustomUser.objects.all().update(is_phone_verified=True)

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_customuser_caste_customuser_sub_caste'),
    ]

    operations = [
        migrations.RunPython(verify_existing_users, reverse_code=migrations.RunPython.noop),
    ]
