# Generated by Django 2.0.13 on 2019-10-02 14:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('iati_synchroniser', '0015_merge_20190619_1028'),
    ]

    operations = [
        migrations.AddField(
            model_name='datasetnote',
            name='last_updated_model',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
    ]
