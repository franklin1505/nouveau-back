# Generated by Django 4.2.16 on 2024-12-24 00:25

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('configurations', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('utilisateurs', '0001_initial'),
        ('courses', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='quote',
            name='client',
            field=models.ForeignKey(help_text='Client associated with the quote.', on_delete=django.db.models.deletion.CASCADE, related_name='quotes', to='utilisateurs.client'),
        ),
        migrations.AddField(
            model_name='quote',
            name='estimates',
            field=models.ManyToManyField(blank=True, help_text='Estimates included in this quote.', related_name='quotes', to='courses.estimate'),
        ),
        migrations.AddField(
            model_name='passenger',
            name='client',
            field=models.ForeignKey(help_text='Client associated with this passenger.', on_delete=django.db.models.deletion.CASCADE, related_name='passengers', to='utilisateurs.client'),
        ),
        migrations.AddField(
            model_name='invoice',
            name='bookings',
            field=models.ManyToManyField(help_text='Bookings associated with the invoice.', related_name='invoices', to='courses.booking'),
        ),
        migrations.AddField(
            model_name='invoice',
            name='client',
            field=models.ForeignKey(blank=True, help_text='Client associated with the invoice.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='invoices', to='utilisateurs.client'),
        ),
        migrations.AddField(
            model_name='invoice',
            name='payment_method',
            field=models.ForeignKey(blank=True, help_text='Payment method used for the invoice.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='invoices', to='configurations.paymentmethod'),
        ),
        migrations.AddField(
            model_name='feedback',
            name='booking',
            field=models.ForeignKey(help_text='booking associated with this feedback.', on_delete=django.db.models.deletion.CASCADE, related_name='feedbacks', to='courses.booking'),
        ),
        migrations.AddField(
            model_name='feedback',
            name='client',
            field=models.ForeignKey(help_text='Client providing the feedback.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='feedbacks', to='utilisateurs.client'),
        ),
        migrations.AddField(
            model_name='feedback',
            name='driver',
            field=models.ForeignKey(blank=True, help_text='Driver associated with the feedback.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='feedbacks', to='utilisateurs.driver'),
        ),
        migrations.AddField(
            model_name='estimateattribute',
            name='attribute',
            field=models.ForeignKey(help_text='Reference to the attribute defined in the business configuration.', on_delete=django.db.models.deletion.CASCADE, to='configurations.attribute'),
        ),
        migrations.AddField(
            model_name='estimateattribute',
            name='estimation',
            field=models.ForeignKey(help_text='Estimation linked to this attribute.', on_delete=django.db.models.deletion.CASCADE, related_name='estimation_attributes', to='courses.estimate'),
        ),
        migrations.AddField(
            model_name='estimate',
            name='estimated_transport_costs',
            field=models.ManyToManyField(blank=True, help_text='All estimated transport costs.', related_name='estimated_costs', to='courses.transportcost'),
        ),
        migrations.AddField(
            model_name='estimate',
            name='meeting_place',
            field=models.ForeignKey(blank=True, help_text='Meeting place associated with the estimate.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='estimates', to='configurations.meetingplace'),
        ),
        migrations.AddField(
            model_name='estimate',
            name='passengers',
            field=models.ManyToManyField(help_text='Passengers associated with this estimate.', related_name='estimates', to='courses.passenger'),
        ),
        migrations.AddField(
            model_name='estimate',
            name='payment_method',
            field=models.ForeignKey(blank=True, help_text='Payment method associated with the estimate.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='estimates', to='configurations.paymentmethod'),
        ),
        migrations.AddField(
            model_name='estimate',
            name='transport_cost',
            field=models.ForeignKey(blank=True, help_text='Final selected transport cost.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='estimates', to='courses.transportcost'),
        ),
        migrations.AddField(
            model_name='bookinglog',
            name='booking',
            field=models.ForeignKey(help_text='Booking associated with this log entry.', on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='courses.booking'),
        ),
        migrations.AddField(
            model_name='bookinglog',
            name='user',
            field=models.ForeignKey(blank=True, help_text='User who performed the action.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='booking_logs', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='booking',
            name='assigned_driver',
            field=models.ForeignKey(blank=True, help_text='Driver assigned to the booking.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='driver_bookings', to='utilisateurs.driver'),
        ),
        migrations.AddField(
            model_name='booking',
            name='assigned_partner',
            field=models.ForeignKey(blank=True, help_text='Partner assigned to the booking.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='partner_bookings', to='utilisateurs.partner'),
        ),
        migrations.AddField(
            model_name='booking',
            name='client',
            field=models.ForeignKey(blank=True, help_text='Client associated with the booking.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='bookings', to='utilisateurs.client'),
        ),
        migrations.AddField(
            model_name='booking',
            name='estimate',
            field=models.ForeignKey(help_text='Estimate associated with the booking.', on_delete=django.db.models.deletion.CASCADE, related_name='bookings', to='courses.estimate'),
        ),
        migrations.AddField(
            model_name='additionaldata',
            name='invoice',
            field=models.ForeignKey(help_text='Invoice associated with this additional data.', on_delete=django.db.models.deletion.CASCADE, related_name='additional_data', to='courses.invoice'),
        ),
    ]
