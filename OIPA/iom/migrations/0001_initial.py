# -*- coding: utf-8 -*-
# Generated by Django 1.11.10 on 2018-12-12 09:47
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('iati', '0006_auto_20170831_1655'),
        ('iati_codelists', '0003_auto_20170704_1525'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProjectType',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activity', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='iati.Activity')),
                ('sector', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='iati_codelists.Sector')),
            ],
        ),
    ]