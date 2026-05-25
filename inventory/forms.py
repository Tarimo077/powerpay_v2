import csv
from collections import OrderedDict
from io import StringIO

from django import forms

from .models import Warehouse, InventoryItem, InventoryMovement


class WarehouseForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        fields = ["name", "location", "organization"]


class InventoryItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = [
            "name",
            "serial_number",
            "product_type",
            "item_type",
            "quantity",
            "current_warehouse",
        ]

    def clean(self):
        cleaned_data = super().clean()
        item_type = cleaned_data.get("item_type")
        quantity = cleaned_data.get("quantity") or 0

        if item_type == InventoryItem.TYPE_UNIQUE:
            cleaned_data["quantity"] = 1

        elif item_type == InventoryItem.TYPE_SHARED and quantity < 1:
            self.add_error(
                "quantity",
                "Quantity is required for shared serial number items."
            )

        return cleaned_data


class BulkInventoryItemForm(forms.Form):
    current_warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.all(),
        widget=forms.Select(attrs={"class": "select select-bordered w-full"}),
    )

    default_name = forms.CharField(
        required=False,
        label="Item name for line entries",
        help_text="Used when you paste serial numbers instead of full CSV rows.",
        widget=forms.TextInput(attrs={
            "class": "input input-bordered w-full",
            "placeholder": "e.g. Smart Meter",
        }),
    )

    default_product_type = forms.CharField(
        required=False,
        label="Product type for line entries",
        help_text="Used when you paste serial numbers instead of full CSV rows.",
        widget=forms.TextInput(attrs={
            "class": "input input-bordered w-full",
            "placeholder": "e.g. Meter",
        }),
    )

    default_item_type = forms.ChoiceField(
        choices=InventoryItem.ITEM_TYPE_CHOICES,
        initial=InventoryItem.TYPE_UNIQUE,
        label="Tracking type for line entries",
        help_text=(
            "Unique items are always saved with quantity 1. "
            "Shared items can use SERIAL,QUANTITY or SERIAL:QUANTITY."
        ),
        widget=forms.Select(attrs={"class": "select select-bordered w-full"}),
    )

    default_quantity = forms.IntegerField(
        required=False,
        min_value=1,
        initial=1,
        label="Default quantity for line entries",
        help_text=(
            "Used for shared line entries when quantity is not written beside the serial. "
            "Ignored for unique items."
        ),
        widget=forms.NumberInput(attrs={
            "class": "input input-bordered w-full",
            "min": "1",
        }),
    )

    csv_file = forms.FileField(
        required=False,
        label="Upload CSV file",
        help_text="Optional. CSV columns: name, serial_number, product_type, item_type, quantity.",
        widget=forms.ClearableFileInput(attrs={
            "class": "file-input file-input-bordered w-full",
            "accept": ".csv,text/csv",
        }),
    )

    csv_data = forms.CharField(
        required=False,
        label="Paste CSV rows or serial numbers",
        widget=forms.Textarea(attrs={
            "class": "textarea textarea-bordered w-full font-mono text-sm",
            "rows": 12,
            "placeholder": (
                "CSV with header:\n"
                "name,serial_number,product_type,item_type,quantity\n"
                "Smart Meter,SM-001,Meter,unique,1\n"
                "Resistor,RES-100,Component,shared,5\n\n"
                "Shared line entries:\n"
                "RES-100,5\n"
                "RES-101:3\n"
                "RES-102|7\n\n"
                "Unique line entries:\n"
                "SM-001\n"
                "SM-002, SM-003, SM-004"
            ),
        }),
        help_text=(
            "Paste a full CSV with header, or paste serial entries. "
            "For shared items, use SERIAL,QUANTITY / SERIAL:QUANTITY / SERIAL|QUANTITY."
        ),
    )

    def _parse_csv_rows(self, raw_csv):
        reader = csv.DictReader(StringIO(raw_csv))
        required_columns = {
            "name",
            "serial_number",
            "product_type",
            "item_type",
            "quantity",
        }

        if not reader.fieldnames or not required_columns.issubset(set(reader.fieldnames)):
            raise forms.ValidationError(
                "CSV header must include: name, serial_number, product_type, item_type, quantity."
            )

        rows = []
        errors = []

        for line_number, row in enumerate(reader, start=2):
            name = (row.get("name") or "").strip()
            serial_number = (row.get("serial_number") or "").strip()
            product_type = (row.get("product_type") or "").strip()
            item_type = (row.get("item_type") or InventoryItem.TYPE_UNIQUE).strip().lower()
            quantity_value = (row.get("quantity") or "").strip()

            if item_type not in {
                InventoryItem.TYPE_UNIQUE,
                InventoryItem.TYPE_SHARED,
            }:
                errors.append(
                    f"Line {line_number}: item_type must be unique or shared."
                )
                continue

            if not name or not serial_number or not product_type:
                errors.append(
                    f"Line {line_number}: name, serial_number and product_type are required."
                )
                continue

            try:
                quantity = int(quantity_value or 1)
            except ValueError:
                errors.append(f"Line {line_number}: quantity must be a number.")
                continue

            if item_type == InventoryItem.TYPE_UNIQUE:
                quantity = 1
            elif quantity < 1:
                errors.append(
                    f"Line {line_number}: quantity must be at least 1 for shared items."
                )
                continue

            rows.append({
                "name": name,
                "serial_number": serial_number,
                "product_type": product_type,
                "item_type": item_type,
                "quantity": quantity,
            })

        if errors:
            raise forms.ValidationError(errors)

        return rows

    def _parse_shared_line_entry(self, value, default_quantity, line_number):
        value = value.strip()

        if not value:
            return None

        serial_number = value
        quantity = default_quantity

        for separator in (":", "|"):
            if separator in value:
                serial_number, quantity_value = [
                    part.strip()
                    for part in value.rsplit(separator, 1)
                ]
                break
        else:
            parts = [part.strip() for part in value.split(",")]
            if len(parts) == 2 and parts[1].isdigit():
                serial_number = parts[0]
                quantity_value = parts[1]
            else:
                quantity_value = None

        if quantity_value is not None:
            try:
                quantity = int(quantity_value)
            except ValueError:
                raise forms.ValidationError(
                    f"Line {line_number}: quantity must be a number."
                )

        if not serial_number:
            raise forms.ValidationError(
                f"Line {line_number}: serial number is required."
            )

        if quantity < 1:
            raise forms.ValidationError(
                f"Line {line_number}: quantity must be at least 1."
            )

        return serial_number, quantity

    def _parse_line_rows(self, raw_lines, defaults):
        item_type = defaults["item_type"]
        rows_by_serial = OrderedDict()
        errors = []

        for line_number, raw_line in enumerate(raw_lines.splitlines(), start=1):
            line = raw_line.strip()

            if not line:
                continue

            if item_type == InventoryItem.TYPE_SHARED:
                try:
                    parsed = self._parse_shared_line_entry(
                        line,
                        defaults["quantity"],
                        line_number,
                    )
                except forms.ValidationError as exc:
                    errors.extend(exc.messages)
                    continue

                if not parsed:
                    continue

                serial_number, quantity = parsed

                if serial_number in rows_by_serial:
                    rows_by_serial[serial_number]["quantity"] += quantity
                else:
                    rows_by_serial[serial_number] = {
                        "name": defaults["name"],
                        "serial_number": serial_number,
                        "product_type": defaults["product_type"],
                        "item_type": item_type,
                        "quantity": quantity,
                    }

            else:
                # Unique items support one per line or comma-separated serials.
                serial_numbers = [
                    token.strip()
                    for token in line.split(",")
                    if token.strip()
                ]

                for serial_number in serial_numbers:
                    if serial_number not in rows_by_serial:
                        rows_by_serial[serial_number] = {
                            "name": defaults["name"],
                            "serial_number": serial_number,
                            "product_type": defaults["product_type"],
                            "item_type": InventoryItem.TYPE_UNIQUE,
                            "quantity": 1,
                        }

        if errors:
            raise forms.ValidationError(errors)

        if not rows_by_serial:
            raise forms.ValidationError("Enter at least one serial number.")

        return list(rows_by_serial.values())

    def clean(self):
        cleaned_data = super().clean()
        csv_file = cleaned_data.get("csv_file")
        pasted_data = (cleaned_data.get("csv_data") or "").strip()

        if csv_file and pasted_data:
            raise forms.ValidationError(
                "Use either a CSV file or pasted entries, not both."
            )

        if not csv_file and not pasted_data:
            raise forms.ValidationError(
                "Upload a CSV file, paste CSV rows, or paste serial numbers."
            )

        raw_data = pasted_data
        source_is_file = False

        if csv_file:
            source_is_file = True

            try:
                raw_data = csv_file.read().decode("utf-8-sig").strip()
            except UnicodeDecodeError:
                raise forms.ValidationError("CSV file must be UTF-8 encoded.")

            if not raw_data:
                raise forms.ValidationError("The uploaded CSV file is empty.")

        first_line = raw_data.splitlines()[0].strip().lower() if raw_data else ""

        looks_like_csv = source_is_file or (
            "name" in first_line
            and "serial_number" in first_line
            and "," in first_line
        )

        if looks_like_csv:
            rows = self._parse_csv_rows(raw_data)
        else:
            default_name = (cleaned_data.get("default_name") or "").strip()
            default_product_type = (
                cleaned_data.get("default_product_type") or ""
            ).strip()
            default_item_type = (
                cleaned_data.get("default_item_type")
                or InventoryItem.TYPE_UNIQUE
            )
            default_quantity = cleaned_data.get("default_quantity") or 1

            if not default_name:
                self.add_error(
                    "default_name",
                    "Item name is required for line-by-line entries."
                )

            if not default_product_type:
                self.add_error(
                    "default_product_type",
                    "Product type is required for line-by-line entries."
                )

            if default_item_type == InventoryItem.TYPE_SHARED and default_quantity < 1:
                self.add_error(
                    "default_quantity",
                    "Quantity is required for shared serial number items."
                )

            if self.errors:
                return cleaned_data

            rows = self._parse_line_rows(
                raw_data,
                {
                    "name": default_name,
                    "product_type": default_product_type,
                    "item_type": default_item_type,
                    "quantity": default_quantity,
                },
            )

        if not rows:
            raise forms.ValidationError("No valid inventory rows found.")

        self.cleaned_rows = rows
        return cleaned_data


class InventoryMoveForm(forms.ModelForm):
    quantity_to_move = forms.IntegerField(
        required=False,
        min_value=1,
        label="Quantity to move",
        help_text=(
            "For shared serial items, leave blank to move all available quantity. "
            "Unique items always move as quantity 1."
        ),
        widget=forms.NumberInput(attrs={
            "class": "input input-bordered w-full",
            "min": "1",
            "placeholder": "Leave blank to move all",
        }),
    )

    class Meta:
        model = InventoryMovement
        fields = ["to_warehouse", "note"]
        widgets = {
            "to_warehouse": forms.Select(attrs={
                "class": "select select-bordered w-full",
            }),
            "note": forms.Textarea(attrs={
                "class": "textarea textarea-bordered w-full",
                "rows": 3,
            }),
        }

    def __init__(self, *args, item=None, allowed_warehouses=None, **kwargs):
        self.item = item
        super().__init__(*args, **kwargs)

        warehouse_qs = (
            allowed_warehouses
            if allowed_warehouses is not None
            else Warehouse.objects.all()
        )

        if item:
            warehouse_qs = warehouse_qs.exclude(id=item.current_warehouse_id)

        self.fields["to_warehouse"].queryset = warehouse_qs

        if item and item.item_type == InventoryItem.TYPE_UNIQUE:
            self.fields["quantity_to_move"].initial = 1
            self.fields["quantity_to_move"].disabled = True
            self.fields["quantity_to_move"].help_text = (
                "Unique serial number items always move as quantity 1."
            )

    def clean_quantity_to_move(self):
        quantity = self.cleaned_data.get("quantity_to_move")

        if not self.item:
            return quantity or 1

        if self.item.item_type == InventoryItem.TYPE_UNIQUE:
            return 1

        if quantity is None:
            quantity = self.item.quantity

        if quantity < 1:
            raise forms.ValidationError("Quantity must be at least 1.")

        if quantity > self.item.quantity:
            raise forms.ValidationError(
                f"Only {self.item.quantity} available in the current warehouse."
            )

        return quantity


class BulkInventoryMoveForm(forms.Form):
    from_warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.none(),
        required=True,
        label="Move from warehouse",
        help_text=(
            "Required. Shared serial items may exist in multiple warehouses, "
            "so the source warehouse must be selected."
        ),
        widget=forms.Select(attrs={"class": "select select-bordered w-full"}),
    )

    to_warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.none(),
        label="Move to warehouse",
        widget=forms.Select(attrs={"class": "select select-bordered w-full"}),
    )

    serial_numbers = forms.CharField(
        label="Serial numbers and quantities",
        help_text=(
            "Use SERIAL to move all available quantity from the source warehouse, "
            "or SERIAL,QUANTITY / SERIAL:QUANTITY to move part of a shared item."
        ),
        widget=forms.Textarea(attrs={
            "class": "textarea textarea-bordered w-full font-mono text-sm",
            "rows": 12,
            "placeholder": "SM-001\nSM-002\nRES-100,2\nRES-101:3",
        }),
    )

    note = forms.CharField(
        required=False,
        label="Note",
        widget=forms.Textarea(attrs={
            "class": "textarea textarea-bordered w-full",
            "rows": 3,
            "placeholder": "Optional movement note",
        }),
    )

    def __init__(self, *args, allowed_warehouses=None, **kwargs):
        super().__init__(*args, **kwargs)

        warehouse_qs = (
            allowed_warehouses
            if allowed_warehouses is not None
            else Warehouse.objects.none()
        )

        self.fields["from_warehouse"].queryset = warehouse_qs
        self.fields["to_warehouse"].queryset = warehouse_qs

    def _parse_move_entry(self, value, line_number):
        value = value.strip()

        if not value:
            return None

        serial_number = value
        quantity = None

        for separator in (":", "|"):
            if separator in value:
                serial_number, quantity_value = [
                    part.strip()
                    for part in value.rsplit(separator, 1)
                ]
                break
        else:
            parts = [part.strip() for part in value.split(",")]

            if len(parts) == 2 and parts[1].isdigit():
                serial_number = parts[0]
                quantity_value = parts[1]
            else:
                quantity_value = None

        if quantity_value is not None:
            try:
                quantity = int(quantity_value)
            except ValueError:
                raise forms.ValidationError(
                    f"Line {line_number}: quantity must be a number."
                )

            if quantity < 1:
                raise forms.ValidationError(
                    f"Line {line_number}: quantity must be at least 1."
                )

        if not serial_number:
            raise forms.ValidationError(
                f"Line {line_number}: serial number is required."
            )

        return serial_number, quantity

    def clean_serial_numbers(self):
        raw = self.cleaned_data["serial_numbers"]
        entries_by_serial = OrderedDict()
        errors = []

        for line_number, raw_line in enumerate(raw.splitlines(), start=1):
            line = raw_line.strip()

            if not line:
                continue

            parts = [part.strip() for part in line.split(",")]
            is_quantity_pair = len(parts) == 2 and parts[1].isdigit()

            if "," in line and not is_quantity_pair and ":" not in line and "|" not in line:
                tokens = [part for part in parts if part]
            else:
                tokens = [line]

            for token in tokens:
                try:
                    parsed = self._parse_move_entry(token, line_number)
                except forms.ValidationError as exc:
                    errors.extend(exc.messages)
                    continue

                if not parsed:
                    continue

                serial_number, quantity = parsed

                if serial_number in entries_by_serial:
                    existing = entries_by_serial[serial_number]

                    # None means "move all available".
                    if existing["quantity"] is None or quantity is None:
                        existing["quantity"] = None
                    else:
                        existing["quantity"] += quantity
                else:
                    entries_by_serial[serial_number] = {
                        "serial_number": serial_number,
                        "quantity": quantity,
                    }

        if errors:
            raise forms.ValidationError(errors)

        if not entries_by_serial:
            raise forms.ValidationError("Enter at least one serial number.")

        return list(entries_by_serial.values())

    def clean(self):
        cleaned_data = super().clean()
        from_warehouse = cleaned_data.get("from_warehouse")
        to_warehouse = cleaned_data.get("to_warehouse")

        if from_warehouse and to_warehouse and from_warehouse.id == to_warehouse.id:
            raise forms.ValidationError(
                "Source and destination warehouses cannot be the same."
            )

        return cleaned_data