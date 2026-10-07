from django.db import migrations
from django.contrib.postgres.operations import TrigramExtension
from django.contrib.postgres.indexes import GinIndex


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0011_alter_customuser_options_customuser_user_match_idx_and_more'),
    ]

    operations = [
        TrigramExtension(),
        migrations.AddIndex(
            model_name='customuser',
            index=GinIndex(
                fields=['full_name'],
                name='user_fn_trgm_idx',
                opclasses=['gin_trgm_ops'],
            ),
        ),
        migrations.AddIndex(
            model_name='customuser',
            index=GinIndex(
                fields=['occupation'],
                name='user_occ_trgm_idx',
                opclasses=['gin_trgm_ops'],
            ),
        ),
    ]
