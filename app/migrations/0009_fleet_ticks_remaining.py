# Generated by Django 3.1 on 2020-08-18 05:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0008_roundparams'),
    ]

    operations = [
        migrations.AddField(
            model_name='fleet',
            name='ticks_remaining',
            field=models.IntegerField(default=0),
        ),
    ]