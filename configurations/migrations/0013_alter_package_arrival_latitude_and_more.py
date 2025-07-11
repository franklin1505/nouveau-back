# Generated by Django 4.2.18 on 2025-03-13 11:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('configurations', '0012_alter_vehicle_registration_number'),
    ]

    operations = [
        migrations.AlterField(
            model_name='package',
            name='arrival_latitude',
            field=models.DecimalField(blank=True, decimal_places=8, help_text='Arrival point latitude.', max_digits=9, null=True),
        ),
        migrations.AlterField(
            model_name='package',
            name='arrival_longitude',
            field=models.DecimalField(blank=True, decimal_places=8, help_text='Arrival point longitude.', max_digits=9, null=True),
        ),
        migrations.AlterField(
            model_name='package',
            name='center_latitude',
            field=models.DecimalField(blank=True, decimal_places=8, help_text='Central point latitude.', max_digits=9, null=True),
        ),
        migrations.AlterField(
            model_name='package',
            name='center_longitude',
            field=models.DecimalField(blank=True, decimal_places=8, help_text='Central point longitude.', max_digits=9, null=True),
        ),
        migrations.AlterField(
            model_name='package',
            name='departure_latitude',
            field=models.DecimalField(decimal_places=8, help_text='Departure point latitude.', max_digits=9),
        ),
        migrations.AlterField(
            model_name='package',
            name='departure_longitude',
            field=models.DecimalField(decimal_places=8, help_text='Departure point longitude.', max_digits=9),
        ),
    ]
