"""
Notification service — creates notification records for shift-related events.

Handles:
- New shift published → notify all matching-role active staff
- Booking confirmed → notify the booking user
"""

from sqlalchemy.orm import Session

from app.models.booking import ShiftBooking
from app.models.notification import Notification, NotificationType
from app.models.shift import Shift
from app.models.user import User, UserRole


class NotificationService:
    """Creates and persists shift-related notifications."""

    @staticmethod
    def notify_new_shift(db: Session, shift: Shift) -> int:
        """Create a notification for every active staff user whose job_title
        matches the shift's required_role.

        Returns the number of notifications created.
        """
        staff_users = (
            db.query(User)
            .filter(
                User.role == UserRole.STAFF,
                User.is_active.is_(True),
                User.job_title == shift.required_role,
            )
            .all()
        )

        notifications = [
            Notification(
                user_id=user.id,
                notification_type=NotificationType.NEW_SHIFT,
                title="New shift available",
                message=(
                    f"A new {shift.shift_type.value} shift on "
                    f"{shift.start_time:%Y-%m-%d %H:%M} is available for "
                    f"{shift.required_role.value}s."
                ),
                related_shift_id=shift.id,
            )
            for user in staff_users
        ]

        db.add_all(notifications)
        db.commit()
        return len(notifications)

    @staticmethod
    def notify_booking_confirmed(
        db: Session, booking: ShiftBooking, shift: Shift
    ) -> None:
        """Create a single confirmation notification for the user who booked
        the shift."""
        notification = Notification(
            user_id=booking.user_id,
            notification_type=NotificationType.BOOKING_CONFIRMED,
            title="Booking confirmed",
            message=(
                f"Your booking for the {shift.shift_type.value} shift on "
                f"{shift.start_time:%Y-%m-%d %H:%M} has been confirmed."
            ),
            related_shift_id=shift.id,
        )
        db.add(notification)
        db.commit()
