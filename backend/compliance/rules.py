DEMO_RULES = [
    {
        'rule_id': 'LM-DEMO-001',
        'field': 'product_name',
        'field_label': 'Product Name',
        'required': True,
        'severity': 'high',
        'description': 'Product name must be declared on the package',
        'source': 'Legal Metrology (Packaged Commodities) Rules — Demo Reference',
        'recommendation': 'Ensure the product name is clearly printed on the label.'
    },
    {
        'rule_id': 'LM-DEMO-002',
        'field': 'net_quantity',
        'field_label': 'Net Quantity',
        'required': True,
        'severity': 'high',
        'description': 'Net quantity/weight/volume must be declared',
        'source': 'Legal Metrology (Packaged Commodities) Rules — Demo Reference',
        'recommendation': 'Declare net quantity in standard units (g, kg, ml, L).'
    },
    {
        'rule_id': 'LM-DEMO-003',
        'field': 'mrp',
        'field_label': 'Maximum Retail Price (MRP)',
        'required': True,
        'severity': 'high',
        'description': 'MRP including all taxes must be declared',
        'source': 'Legal Metrology (Packaged Commodities) Rules — Demo Reference',
        'recommendation': 'Print MRP inclusive of all taxes clearly on the package.'
    },
    {
        'rule_id': 'LM-DEMO-004',
        'field': 'manufacturer',
        'field_label': 'Manufacturer/Packer Name & Address',
        'required': True,
        'severity': 'high',
        'description': 'Name and address of manufacturer/packer/importer must be declared',
        'source': 'Legal Metrology (Packaged Commodities) Rules — Demo Reference',
        'recommendation': 'Include complete name and address of the manufacturer or packer.'
    },
    {
        'rule_id': 'LM-DEMO-005',
        'field': 'manufacturing_date',
        'field_label': 'Date of Manufacture/Packing',
        'required': True,
        'severity': 'medium',
        'description': 'Manufacturing or packing date should be declared',
        'source': 'Legal Metrology (Packaged Commodities) Rules — Demo Reference',
        'recommendation': 'Declare the month and year of manufacture or packing.'
    },
    {
        'rule_id': 'LM-DEMO-006',
        'field': 'expiry_date',
        'field_label': 'Best Before/Expiry Date',
        'required': True,
        'severity': 'high',
        'description': 'Best before or expiry date should be declared for consumable products',
        'source': 'Legal Metrology (Packaged Commodities) Rules — Demo Reference',
        'recommendation': 'Declare best before or use by date clearly.'
    },
    {
        'rule_id': 'LM-DEMO-007',
        'field': 'consumer_care',
        'field_label': 'Consumer Care Information',
        'required': True,
        'severity': 'medium',
        'description': 'Consumer care contact details should be provided',
        'source': 'Legal Metrology (Packaged Commodities) Rules — Demo Reference',
        'recommendation': 'Provide customer care phone, email, or address.'
    },
    {
        'rule_id': 'LM-DEMO-008',
        'field': 'country_of_origin',
        'field_label': 'Country of Origin',
        'required': True,
        'severity': 'medium',
        'description': 'Country of origin should be declared, especially for imported goods',
        'source': 'Legal Metrology (Packaged Commodities) Rules — Demo Reference',
        'recommendation': 'Declare the country of origin on the package.'
    },
    {
        'rule_id': 'LM-DEMO-009',
        'field': 'fssai_license',
        'field_label': 'FSSAI License Number',
        'required': True,
        'severity': 'high',
        'description': 'FSSAI license number is required for food products',
        'source': 'FSSAI Regulations — Demo Reference',
        'recommendation': 'Display valid 14-digit FSSAI license number.'
    },
    {
        'rule_id': 'LM-DEMO-010',
        'field': 'ingredients',
        'field_label': 'List of Ingredients',
        'required': True,
        'severity': 'medium',
        'description': 'List of ingredients should be declared for food products',
        'source': 'FSSAI Regulations — Demo Reference',
        'recommendation': 'List all ingredients in descending order of composition.'
    }
]
