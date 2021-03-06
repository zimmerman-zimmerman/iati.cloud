# Generated by Django 2.0.4 on 2018-04-30 14:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('iati_organisation', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organisationnarrative',
            name='object_id',
            field=models.IntegerField(db_index=True, verbose_name='related object'),
        ),
        migrations.AlterField(
            model_name='recipientorgbudget',
            name='recipient_org_identifier',
            field=models.CharField(max_length=150, null=True, verbose_name='recipient_org_identifier'),
        ),
    ]
