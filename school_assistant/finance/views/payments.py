import stripe
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from finance.models import Fee


class CreatePaymentIntentView(APIView):
    """
    POST /api/payments/create-intent
    Creates a Stripe PaymentIntent for a given fee.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        fee_id = request.data.get('fee_id')
        if not fee_id:
            return Response(
                {"error": "fee_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            fee = Fee.objects.select_related('student__user').get(id=fee_id)
        except Fee.DoesNotExist:
            return Response(
                {"error": "Fee not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Authorization check (Student/Parent hi pay kar sakte hain)
        user = request.user
        if user.role.role_name == 'Student':
            if fee.student.user.id != user.id:
                return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        elif user.role.role_name == 'Parent':
            if not fee.student.parents.filter(user=user).exists():
                return Response({"error": "Unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        else:
            return Response({"error": "Only Students and Parents can pay"}, status=status.HTTP_403_FORBIDDEN)

        if fee.status == 'Paid':
            return Response({"error": "Fee already paid"}, status=status.HTTP_400_BAD_REQUEST)

        amount_to_pay = fee.amount - fee.amount_paid
        if amount_to_pay <= 0:
            return Response({"error": "No outstanding balance"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount_to_pay * 100),
                currency='usd',
                metadata={'fee_id': fee.id},
                description=f"Fee for {fee.student.user.full_name} - {fee.month}",
            )

            return Response({
                'client_secret': intent.client_secret,
                'payment_intent_id': intent.id,
                'amount': amount_to_pay,
            }, status=status.HTTP_200_OK)

        except stripe.error.StripeError as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)