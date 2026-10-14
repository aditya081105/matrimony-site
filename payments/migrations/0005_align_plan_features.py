from django.db import migrations


def update_plan_features(apps, schema_editor):
    Plan = apps.get_model('payments', 'Plan')
    plans_data = {
        'silver': {
            'features': (
                "Send up to 10 requests per day\n"
                "Verified Silver badge on profile\n"
                "Highlighted profile visibility\n"
                "Standard customer support"
            ),
        },
        'gold': {
            'features': (
                "Direct phone and email contact unlock\n"
                "Unlimited contact requests\n"
                "Verified Gold badge on profile\n"
                "Boosted search and matchmaking visibility\n"
                "Priority customer support"
            ),
        },
        'diamond': {
            'features': (
                "All Gold features included\n"
                "Direct phone and email contact unlock\n"
                "Top-of-the-list profile placement\n"
                "Elite Diamond badge on profile\n"
                "Dedicated relationship manager profile review"
            ),
        },
    }
    for code, data in plans_data.items():
        Plan.objects.filter(code=code).update(features=data['features'])


def rollback_plan_features(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0004_seed_default_plans'),
    ]

    operations = [
        migrations.RunPython(update_plan_features, rollback_plan_features),
    ]
