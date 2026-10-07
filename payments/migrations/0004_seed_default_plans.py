from django.db import migrations


def seed_plans(apps, schema_editor):
    Plan = apps.get_model('payments', 'Plan')
    default_plans = [
        {
            'code': 'silver',
            'name': 'Silver Plan',
            'price': 199.00,
            'duration_days': 30,
            'badge_label': '',
            'features': "Send up to 10 requests per day\nVerified Silver badge on profile\nHighlighted profile visibility\nStandard customer support",
        },
        {
            'code': 'gold',
            'name': 'Gold Plan',
            'price': 399.00,
            'duration_days': 90,
            'badge_label': 'Popular',
            'features': "Unlimited contact requests\nVerified Gold badge on profile\nBoosted search & matchmaking visibility\nPriority customer support",
        },
        {
            'code': 'diamond',
            'name': 'Diamond VIP',
            'price': 699.00,
            'duration_days': 180,
            'badge_label': 'Best Value',
            'features': "All Gold features included\nTop-of-the-list profile placement\nElite Diamond badge on profile\nRelationship manager profile review",
        },
    ]
    for p in default_plans:
        Plan.objects.get_or_create(code=p['code'], defaults=p)


def rollback_plans(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0003_paymentorder_unique_active_utr_order'),
    ]

    operations = [
        migrations.RunPython(seed_plans, rollback_plans),
    ]
