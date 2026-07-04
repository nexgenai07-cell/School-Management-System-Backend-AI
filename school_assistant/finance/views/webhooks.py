import json
import stripe
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db import transaction, models
from decimal import Decimal

from finance.models import Fee, Payment, FeeHistory


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    POST /api/webhooks/stripe
    Handles Stripe webhook events.
    """
    payload = request.body
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET

    # DEVELOPMENT MODE (Skip signature verification) 
    if settings.DEBUG:
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid payload"}, status=400)
    else:
        #  PRODUCTION MODE (Verify signature)
        if not webhook_secret:
            return JsonResponse({"error": "Webhook secret not configured"}, status=500)

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except stripe.error.SignatureVerificationError:
            return JsonResponse({"error": "Invalid signature"}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid payload"}, status=400)

    event_type = event.get('type')
    event_data = event.get('data', {}).get('object', {})

    if event_type == 'payment_intent.succeeded':
        handle_payment_success(event_data)
    elif event_type == 'payment_intent.payment_failed':
        handle_payment_failure(event_data)

    return JsonResponse({"status": "received"}, status=200)


def handle_payment_success(payment_intent):
    metadata = payment_intent.get('metadata', {})
    fee_id = metadata.get('fee_id')

    if not fee_id:
        print(f"PaymentIntent without fee_id: {payment_intent.get('id')}")
        return

    with transaction.atomic():
        try:
            fee = Fee.objects.select_for_update().get(id=fee_id)
        except Fee.DoesNotExist:
            print(f"Fee not found: {fee_id}")
            return

        # IDEMPOTENCY CHECK: Pehle se payment exist karti hai?
        intent_id = payment_intent.get('id')
        if Payment.objects.filter(transaction_id=intent_id).exists():
            print(f"Duplicate webhook for {intent_id}")
            return

        amount_paid = Decimal(payment_intent.get('amount', 0)) / Decimal(100)

        #  YAHAN transaction_id mein Stripe Intent ID store ho raha hai
        payment = Payment.objects.create(
            fee=fee,
            amount_paid=amount_paid,
            payment_method='Online',
            transaction_id=intent_id,  # <-- Isi field mein store ho raha hai (Model change nahi)
            payment_date=payment_intent.get('created', None)
        )

        old_status = fee.status
        total_paid = fee.payments.aggregate(
            total=models.Sum('amount_paid')
        )['total'] or Decimal(0)

        fee.amount_paid = total_paid
        fee.status = 'Paid' if total_paid >= fee.amount else ('Partial' if total_paid > 0 else 'Unpaid')
        if fee.status == 'Paid':
            fee.paid_date = payment.payment_date
        fee.save()

        if old_status != fee.status:
            FeeHistory.objects.create(
                fee=fee,
                old_status=old_status,
                new_status=fee.status,
                old_amount=fee.amount,
                new_amount=fee.amount,
                changed_by_admin=None,
                reason=f"Online payment via Stripe: {intent_id}"
            )

        print(f" Payment processed: Fee {fee.id}, Status: {fee.status}")


def handle_payment_failure(payment_intent):
    print(f"Payment failed: {payment_intent.get('id')}")
    # TODO: Send email/notification to admin