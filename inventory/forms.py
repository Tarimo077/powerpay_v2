import csv
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
            self.add_error("quantity", "Quantity is required for shared serial number items.")

        return cleaned_data


class BulkInventoryItemForm(forms.Form):
    current_warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.all(),
        widget=forms.Select(attrs={"class": "select select-bordered w-full"}),
    )
    default_name = forms.CharField(
        required=False,
        label="Item name for line entries",
        help_text="Used when you paste one serial number per line.",
        widget=forms.TextInput(attrs={
            "class": "input input-bordered w-full",
            "placeholder": "e.g. Smart Meter",
        }),
    )
    default_product_type = forms.CharField(
        required=False,
        label="Product type for line entries",
        help_text="Used when you paste one serial number per line.",
        widget=forms.TextInput(attrs={
            "class": "input input-bordered w-full",
            "placeholder": "e.g. Meter",
        }),
    )
    default_item_type = forms.ChoiceField(
        choices=InventoryItem.ITEM_TYPE_CHOICES,
        initial=InventoryItem.TYPE_UNIQUE,
        label="Tracking type for line entries",
        help_text="Unique items are always saved with quantity 1. Shared items require a quantity.",
        widget=forms.Select(attrs={"class": "select select-bordered w-full"}),
    )
    default_quantity = forms.IntegerField(
        required=False,
        min_value=1,
        initial=1,
        label="Quantity for line entries",
        help_text="Ignored for unique serial number items.",
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
            "placeholder": "CSV with header:\nname,serial_number,product_type,item_type,quantity\nSmart Meter,SM-001,Meter,unique,1\n\nOr one serial number per line:\nSM-001\nSM-002\nSM-003",
        }),
        help_text=(
            "Paste a full CSV with header, or paste one serial number per line/comma. "
            "Line entries use the item name, product type, tracking type and quantity fields above."
        ),
    )

    def _parse_csv_rows(self, raw_csv):
        reader = csv.DictReader(StringIO(raw_csv))
        required_columns = {"name", "serial_number", "product_type", "item_type", "quantity"}
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

            if item_type not in {InventoryItem.TYPE_UNIQUE, InventoryItem.TYPE_SHARED}:
                errors.append(f"Line {line_number}: item_type must be unique or shared.")
                continue

            if not name or not serial_number or not product_type:
                errors.append(f"Line {line_number}: name, serial_number and product_type are required.")
                continue

            try:
                quantity = int(quantity_value or 1)
            except ValueError:
                errors.append(f"Line {line_number}: quantity must be a number.")
                continue

            if item_type == InventoryItem.TYPE_UNIQUE:
                quantity = 1
            elif quantity < 1:
                errors.append(f"Line {line_number}: quantity must be at least 1 for shared items.")
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

    def _parse_line_rows(self, raw_lines, defaults):
        serial_numbers = []
        seen = set()
        for token in raw_lines.replace(",", "\n").splitlines():
            serial_number = token.strip()
            if not serial_number:
                continue
            if serial_number not in seen:
                serial_numbers.append(serial_number)
                seen.add(serial_number)

        if not serial_numbers:
            raise forms.ValidationError("Enter at least one serial number.")

        item_type = defaults["item_type"]
        quantity = defaults["quantity"]
        if item_type == InventoryItem.TYPE_UNIQUE:
            quantity = 1

        return [
            {
                "name": defaults["name"],
                "serial_number": serial_number,
                "product_type": defaults["product_type"],
                "item_type": item_type,
                "quantity": quantity,
            }
            for serial_number in serial_numbers
        ]

    def clean(self):
        cleaned_data = super().clean()
        csv_file = cleaned_data.get("csv_file")
        pasted_data = (cleaned_data.get("csv_data") or "").strip()

        if csv_file and pasted_data:
            raise forms.ValidationError("Use either a CSV file or pasted entries, not both.")
        if not csv_file and not pasted_data:
            raise forms.ValidationError("Upload a CSV file, paste CSV rows, or paste serial numbers one per line.")

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
            "name" in first_line and "serial_number" in first_line and "," in first_line
        )

        if looks_like_csv:
            rows = self._parse_csv_rows(raw_data)
        else:
            default_name = (cleaned_data.get("default_name") or "").strip()
            default_product_type = (cleaned_data.get("default_product_type") or "").strip()
            default_item_type = cleaned_data.get("default_item_type") or InventoryItem.TYPE_UNIQUE
            default_quantity = cleaned_data.get("default_quantity") or 1

            if not default_name:
                self.add_error("default_name", "Item name is required for line-by-line entries.")
            if not default_product_type:
                self.add_error("default_product_type", "Product type is required for line-by-line entries.")
            if default_item_type == InventoryItem.TYPE_SHARED and default_quantity < 1:
                self.add_error("default_quantity", "Quantity is required for shared serial number items.")
            if self.errors:
                return cleaned_data

            rows = self._parse_line_rows(raw_data, {
                "name": default_name,
                "product_type": default_product_type,
                "item_type": default_item_type,
                "quantity": default_quantity,
            })

        if not rows:
            raise forms.ValidationError("No valid inventory rows found.")

        self.cleaned_rows = rows
        return cleaned_data


class InventoryMoveForm(forms.ModelForm):
    class Meta:
        model = InventoryMovement
        fields = ["to_warehouse", "note"]

    def __init__(self, *args, item=None, **kwargs):
        super().__init__(*args, **kwargs)
        if item:
            self.fields["to_warehouse"].queryset = Warehouse.objects.exclude(id=item.current_warehouse.id)


class BulkInventoryMoveForm(forms.Form):
    from_warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.none(),
        required=False,
        label="Move only items currently in this warehouse",
        help_text="Optional. Use this to prevent moving items from the wrong warehouse.",
        widget=forms.Select(attrs={"class": "select select-bordered w-full"}),
    )

    to_warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.none(),
        label="Move to warehouse",
        widget=forms.Select(attrs={"class": "select select-bordered w-full"}),
    )

    serial_numbers = forms.CharField(
        label="Serial numbers",
        help_text="Paste one serial number per line, or separate them with commas.",
        widget=forms.Textarea(attrs={
            "class": "textarea textarea-bordered w-full font-mono text-sm",
            "rows": 12,
            "placeholder": "SM-001\nSM-002\nSM-003",
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
        warehouse_qs = allowed_warehouses if allowed_warehouses is not None else Warehouse.objects.none()
        self.fields["from_warehouse"].queryset = warehouse_qs
        self.fields["to_warehouse"].queryset = warehouse_qs

    def clean_serial_numbers(self):
        raw = self.cleaned_data["serial_numbers"]
        serials = []
        seen = set()

        for token in raw.replace(",", "\n").splitlines():
            serial = token.strip()
            if not serial:
                continue

            if serial not in seen:
                serials.append(serial)
                seen.add(serial)

        if not serials:
            raise forms.ValidationError("Enter at least one serial number.")

        return serials

    def clean(self):
        cleaned_data = super().clean()
        from_warehouse = cleaned_data.get("from_warehouse")
        to_warehouse = cleaned_data.get("to_warehouse")

        if from_warehouse and to_warehouse and from_warehouse.id == to_warehouse.id:
            raise forms.ValidationError("Source and destination warehouses cannot be the same.")

        return cleaned_data
