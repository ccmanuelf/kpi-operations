"""
QR Code Service for KPI Platform
Handles QR code generation, decoding, and auto-fill field mapping
"""

import json
import logging
import qrcode
from io import BytesIO
from typing import Dict, Any, Optional, Tuple
from pydantic import ValidationError

logger = logging.getLogger(__name__)

from backend.models.qr import QRCodeData, QREntityType


class QRServiceError(Exception):
    """Custom exception for QR service errors"""

    pass


class QRService:
    """
    Service class for QR code operations

    Handles:
    - QR code image generation (PNG)
    - QR data string decoding
    - Auto-fill field mapping for entry forms
    """

    # Version for QR code schema compatibility
    QR_VERSION = "1.0"

    @staticmethod
    def generate_qr_image(data: QRCodeData, size: int = 200) -> bytes:
        """
        Generate QR code PNG image bytes

        Args:
            data: QRCodeData containing type, id, and version
            size: Image size in pixels (default 200)

        Returns:
            PNG image as bytes

        Raises:
            QRServiceError: If QR code generation fails
        """
        try:
            # Serialize data to JSON string
            qr_string = data.model_dump_json()

            # Create QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_string)
            qr.make(fit=True)

            # Generate image
            img = qr.make_image(fill_color="black", back_color="white")

            # Resize to requested size
            img = img.resize((size, size))

            # Convert to bytes
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)

            return buffer.getvalue()

        except (ValueError, TypeError) as e:
            logger.exception("QR code generation failed due to invalid input")
            raise QRServiceError("Failed to generate QR code due to invalid input")
        except (IOError, OSError) as e:
            logger.exception("QR code image generation I/O error")
            raise QRServiceError("Failed to generate QR code image")

    @staticmethod
    def create_qr_data(entity_type: str, entity_id: str) -> QRCodeData:
        """
        Create QRCodeData object for an entity

        Args:
            entity_type: Type of entity (work_order, product, job, employee)
            entity_id: ID of the entity

        Returns:
            QRCodeData object

        Raises:
            QRServiceError: If entity type is invalid
        """
        try:
            return QRCodeData(type=entity_type, id=str(entity_id), version=QRService.QR_VERSION)
        except ValidationError as e:
            raise QRServiceError(f"Invalid entity type: {entity_type}")

    @staticmethod
    def decode_qr_string(qr_string: str) -> QRCodeData:
        """
        Parse JSON string from QR scan into QRCodeData

        Args:
            qr_string: JSON string from QR code scan

        Returns:
            QRCodeData object with parsed type, id, version

        Raises:
            QRServiceError: If string cannot be parsed or is invalid format
        """
        try:
            # Parse JSON
            data = json.loads(qr_string)

            # Validate and create QRCodeData
            return QRCodeData(**data)

        except json.JSONDecodeError as e:
            raise QRServiceError(f"Invalid QR code format: not valid JSON - {str(e)}")
        except ValidationError as e:
            raise QRServiceError(f"Invalid QR code data: {str(e)}")
        except (TypeError, KeyError) as e:
            logger.exception("QR string decoding failed due to unexpected data format")
            raise QRServiceError("Failed to decode QR string due to unexpected data format")

    @staticmethod
    def get_auto_fill_fields(entity_type: str, entity_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Return fields to auto-populate in entry forms based on entity type

        Args:
            entity_type: Type of entity (work_order, product, job, employee)
            entity_data: Full entity data from database

        Returns:
            Dictionary of field names and values for form auto-population

        Field mappings:
        - work_order -> work_order_id, client_id, product_id (if available), planned_quantity, style_model
        - product -> product_id, product_name, ideal_cycle_time
        - job -> job_id, work_order_id, client_id, operation_name, part_number
        - employee -> employee_id, employee_code, employee_name
        """
        auto_fill = {}

        if entity_type == QREntityType.WORK_ORDER or entity_type == "work_order":
            # Work order fields for production/quality/downtime entry forms
            auto_fill = {
                "work_order_id": entity_data.get("work_order_id"),
                "work_order_number": entity_data.get("work_order_id"),  # Alias
                "client_id": entity_data.get("client_id"),
                "planned_quantity": entity_data.get("planned_quantity"),
                "style_model": entity_data.get("style_model"),
                "status": entity_data.get("status"),
            }

            # Include ideal_cycle_time if available
            if entity_data.get("ideal_cycle_time"):
                auto_fill["ideal_cycle_time"] = entity_data.get("ideal_cycle_time")

            # Include priority if available
            if entity_data.get("priority"):
                auto_fill["priority"] = entity_data.get("priority")

        elif entity_type == QREntityType.PRODUCT or entity_type == "product":
            # Product fields for production entry forms
            auto_fill = {
                "product_id": entity_data.get("product_id"),
                "product_code": entity_data.get("product_code"),
                "product_name": entity_data.get("product_name"),
            }

            # Include ideal_cycle_time if defined on product
            if entity_data.get("ideal_cycle_time"):
                auto_fill["ideal_cycle_time"] = entity_data.get("ideal_cycle_time")

        elif entity_type == QREntityType.JOB or entity_type == "job":
            # Job fields for detailed entry forms
            auto_fill = {
                "job_id": entity_data.get("job_id"),
                "work_order_id": entity_data.get("work_order_id"),
                "client_id": entity_data.get("client_id_fk"),
                "operation_name": entity_data.get("operation_name"),
                "operation_code": entity_data.get("operation_code"),
                "part_number": entity_data.get("part_number"),
                "part_description": entity_data.get("part_description"),
                "planned_quantity": entity_data.get("planned_quantity"),
                "sequence_number": entity_data.get("sequence_number"),
            }

            # Include assigned resources if available
            if entity_data.get("assigned_employee_id"):
                auto_fill["assigned_employee_id"] = entity_data.get("assigned_employee_id")
            if entity_data.get("assigned_shift_id"):
                auto_fill["shift_id"] = entity_data.get("assigned_shift_id")

        elif entity_type == QREntityType.EMPLOYEE or entity_type == "employee":
            # Employee fields for attendance/assignment forms
            auto_fill = {
                "employee_id": entity_data.get("employee_id"),
                "employee_code": entity_data.get("employee_code"),
                "employee_name": entity_data.get("employee_name"),
                "department": entity_data.get("department"),
                "position": entity_data.get("position"),
            }

            # Include client assignment if available
            if entity_data.get("client_id_assigned"):
                auto_fill["client_id_assigned"] = entity_data.get("client_id_assigned")

            # Include floating pool status
            auto_fill["is_floating_pool"] = entity_data.get("is_floating_pool", 0)

        # Remove None values for cleaner response
        auto_fill = {k: v for k, v in auto_fill.items() if v is not None}

        return auto_fill

    @staticmethod
    def validate_entity_type(entity_type: str) -> bool:
        """
        Validate that entity_type is a supported QR entity type

        Args:
            entity_type: String to validate

        Returns:
            True if valid, False otherwise
        """
        valid_types = [e.value for e in QREntityType]
        return entity_type in valid_types or entity_type in [e.name.lower() for e in QREntityType]

    @staticmethod
    def get_qr_data_string(entity_type: str, entity_id: str) -> str:
        """
        Generate the JSON string that will be encoded in a QR code

        Args:
            entity_type: Type of entity
            entity_id: ID of entity

        Returns:
            JSON string for QR code
        """
        data = QRCodeData(type=entity_type, id=str(entity_id), version=QRService.QR_VERSION)
        return data.model_dump_json()
