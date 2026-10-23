import uuid
from decimal import Decimal
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from core.tenancy.models import TenantAwareModel


class PaymentOrder(TenantAwareModel):
    """
    Unified payment order tracking customer checkouts for courses, books,
    and exam bundles through the Webkoders MFS payment gateway.
    """

    class OrderType(models.TextChoices):
        COURSE = "course", "Course Enrollment"
        EXAM_GROUP = "exam_group", "Exam Bundle / Group"
        BOOK = "book", "Book Purchase"
        GENERAL = "general", "General Payment"

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "অপেক্ষমান (Pending)"
        PAID = "PAID", "সফল (Paid)"
        FAILED = "FAILED", "ব্যর্থ (Failed)"
        CANCELLED = "CANCELLED", "বাতিল (Cancelled)"

    order_no = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Unique public or local order tracking code.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_orders",
        help_text="Customer / student placing the order.",
    )
    order_type = models.CharField(
        max_length=32,
        choices=OrderType.choices,
        default=OrderType.COURSE,
        db_index=True,
    )
    course = models.ForeignKey(
        "courses.Course",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payment_orders",
    )
    exam_group = models.ForeignKey(
        "courses.ExamGroup",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payment_orders",
    )
    book_order = models.ForeignKey(
        "courses.BookOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="payment_orders",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Order payable amount in BDT.",
    )
    currency = models.CharField(max_length=10, default="BDT")
    customer_name = models.CharField(max_length=150, blank=True, default="")
    customer_email = models.CharField(max_length=150, blank=True, default="")
    customer_phone = models.CharField(max_length=50, blank=True, default="")
    payment_status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
    )
    gateway_reference = models.CharField(
        max_length=100,
        blank=True,
        default="",
        db_index=True,
        help_text="Unique reference UUID returned by the gateway invoice.",
    )
    gateway_trx_id = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="SMS Forwarded MFS transaction ID from bKash/Nagad/Rocket.",
    )
    gateway_checkout_url = models.URLField(
        max_length=500,
        blank=True,
        default="",
        help_text="Hosted checkout URL for student redirection.",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Custom key-value parameters passed through checkout.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "payment_status"]),
            models.Index(fields=["gateway_reference"]),
            models.Index(fields=["order_no"]),
        ]

    def __str__(self):
        return f"Order #{self.order_no} ({self.get_order_type_display()} - {self.amount} BDT) - {self.payment_status}"

    def save(self, *args, **kwargs):
        if not self.order_no:
            prefix = "ORD"
            if self.order_type == self.OrderType.COURSE:
                prefix = "CRS"
            elif self.order_type == self.OrderType.EXAM_GROUP:
                prefix = "GRP"
            elif self.order_type == self.OrderType.BOOK:
                prefix = "BOK"
            self.order_no = f"{prefix}-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    @transaction.atomic
    def fulfill_order(self):
        """
        Fulfills course enrollment, exam group access, or book status atomically
        upon payment completion. Safe for idempotent re-runs.
        """
        from apps.courses.models import (
            Enrollment,
            ExamGroupEnrollment,
            StudentInvoice,
            FinancialLedger,
            BookOrder,
        )

        tenant = self.tenant
        user = self.user

        # 1. Course Enrollment
        if self.order_type == self.OrderType.COURSE and self.course:
            enrollment, _ = Enrollment.objects.get_or_create(
                tenant=tenant,
                user=user,
                course=self.course,
                defaults={"status": Enrollment.Status.ACTIVE},
            )
            if enrollment.status != Enrollment.Status.ACTIVE:
                enrollment.status = Enrollment.Status.ACTIVE
                enrollment.save(update_fields=["status"])

            # Create or update StudentInvoice
            inv_no = f"INV-{self.order_no}"
            invoice, created = StudentInvoice.objects.get_or_create(
                tenant=tenant,
                student=user,
                invoice_no=inv_no,
                defaults={
                    "item_title": f"Course: {self.course.title}",
                    "amount": self.amount,
                    "payment_method": "Webkoders Online Gateway",
                    "transaction_id": self.gateway_trx_id or self.order_no,
                    "status": "PAID",
                },
            )
            if not created and invoice.status != "PAID":
                invoice.status = "PAID"
                invoice.transaction_id = self.gateway_trx_id or invoice.transaction_id
                invoice.save(update_fields=["status", "transaction_id"])

            # Financial ledger entry
            FinancialLedger.objects.get_or_create(
                tenant=tenant,
                description=f"Course Purchase: {self.course.title} by {user.email}",
                amount=self.amount,
                entry_type="CREDIT",
                category="COURSE_SALE",
            )

        # 2. Exam Group Enrollment
        elif self.order_type == self.OrderType.EXAM_GROUP and self.exam_group:
            grp_enrollment, _ = ExamGroupEnrollment.objects.get_or_create(
                tenant=tenant,
                user=user,
                group=self.exam_group,
                defaults={
                    "is_paid": True,
                    "paid_amount": self.amount,
                    "payment_method": "Webkoders Online Gateway",
                    "transaction_id": self.gateway_trx_id or self.order_no,
                },
            )
            if not grp_enrollment.is_paid:
                grp_enrollment.is_paid = True
                grp_enrollment.paid_amount = self.amount
                grp_enrollment.payment_method = "Webkoders Online Gateway"
                grp_enrollment.transaction_id = self.gateway_trx_id or self.order_no
                grp_enrollment.save(update_fields=["is_paid", "paid_amount", "payment_method", "transaction_id"])

            # Create or update StudentInvoice
            inv_no = f"INV-GRP-{self.order_no}"
            invoice, created = StudentInvoice.objects.get_or_create(
                tenant=tenant,
                student=user,
                invoice_no=inv_no,
                defaults={
                    "item_title": f"Model Test Group: {self.exam_group.title}",
                    "amount": self.amount,
                    "payment_method": "Webkoders Online Gateway",
                    "transaction_id": self.gateway_trx_id or self.order_no,
                    "status": "PAID",
                },
            )
            if not created and invoice.status != "PAID":
                invoice.status = "PAID"
                invoice.transaction_id = self.gateway_trx_id or invoice.transaction_id
                invoice.save(update_fields=["status", "transaction_id"])

            FinancialLedger.objects.get_or_create(
                tenant=tenant,
                description=f"Exam Group Purchase: {self.exam_group.title} by {user.email}",
                amount=self.amount,
                entry_type="CREDIT",
                category="EXAM_SALE",
            )

        # 3. Book Order
        elif self.order_type == self.OrderType.BOOK and self.book_order:
            if self.book_order.status == BookOrder.Status.PENDING:
                self.book_order.status = BookOrder.Status.PROCESSING
                if self.gateway_trx_id:
                    self.book_order.tracking_number = self.gateway_trx_id
                self.book_order.save(update_fields=["status", "tracking_number"])

            inv_no = f"INV-BOK-{self.order_no}"
            StudentInvoice.objects.get_or_create(
                tenant=tenant,
                student=user,
                invoice_no=inv_no,
                defaults={
                    "item_title": f"Book: {self.book_order.book.title}",
                    "amount": self.amount,
                    "payment_method": "Webkoders Online Gateway",
                    "transaction_id": self.gateway_trx_id or self.order_no,
                    "status": "PAID",
                },
            )

    def get_success_redirect_url(self):
        """
        Returns destination URL for customer once payment is confirmed.
        """
        if self.order_type == self.OrderType.COURSE and self.course:
            first_lesson = (
                self.course.modules.prefetch_related("lessons")
                .order_by("order")
                .first()
            )
            if first_lesson:
                l = first_lesson.lessons.order_by("order").first()
                if l:
                    return f"/courses/{self.course.slug}/lessons/{l.slug}/"
            return f"/courses/{self.course.slug}/"

        elif self.order_type == self.OrderType.EXAM_GROUP and self.exam_group:
            return f"/exams/groups/{self.exam_group.slug}/"

        elif self.order_type == self.OrderType.BOOK and self.book_order:
            return "/dashboard/"

        return "/dashboard/"

