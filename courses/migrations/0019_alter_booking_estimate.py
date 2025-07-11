# Generated by Django 4.2.18 on 2025-07-09 09:26

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0018_booking_booking_type_bookingsegment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='booking',
            name='estimate',
            field=models.ForeignKey(blank=True, help_text='Estimate associated with the booking.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bookings', to='courses.estimate'),
        ),
    ]
