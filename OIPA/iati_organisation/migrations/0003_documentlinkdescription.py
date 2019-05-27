# Generated by Django 2.0.13 on 2019-05-21 09:47

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('iati_organisation', '0002_auto_20180430_1400'),
    ]

    operations = [
        migrations.CreateModel(
            name='DocumentLinkDescription',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('document_link', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='iati_organisation.OrganisationDocumentLink')),
            ],
        ),
    ]
