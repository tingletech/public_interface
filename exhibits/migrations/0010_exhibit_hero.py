# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2016-03-07 20:55
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('exhibits', '0009_auto_20160302_2314'),
    ]

    operations = [
        migrations.AddField(
            model_name='exhibit',
            name='hero',
            field=models.ImageField(blank=True, upload_to='uploads/', verbose_name='Hero Image'),
        ),
    ]