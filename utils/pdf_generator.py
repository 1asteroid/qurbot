"""PDF receipt and report generators"""
from io import BytesIO
from datetime import datetime
import pytz
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from config import settings

TZ = pytz.timezone(settings.TIMEZONE)


def _item_suffix(item) -> str:
    category_name = (item.product.category.name if item.product and item.product.category else "").strip().lower()
    if not item.size:
        return ""
    if category_name == "travertin":
        return f" | Rang: {item.size}"
    if category_name == "tiya":
        return f" | Razmer: {item.size}"
    return f" | {item.size}"

# Font to support Cyrillic (if needed), using default for now
def get_styles():
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=12,
        alignment=1,  # Center
    )
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#333333'),
        spaceAfter=6,
    )
    return styles, title_style, header_style


def generate_receipt_pdf(order) -> BytesIO:
    """Generate order receipt PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.7*cm, bottomMargin=0.7*cm)
    
    styles, title_style, header_style = get_styles()
    elements = []
    
    # Company header
    company_header = Paragraph(
        "«NOVASTONE» FIRMA<br/>"
        "<font size='9'>Qurilish materiallari do'koni</font>",
        ParagraphStyle(
            'CompanyHeader',
            parent=styles['Normal'],
            fontSize=12,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#1a1a1a'),
            alignment=1,
            spaceAfter=8,
        )
    )
    elements.append(company_header)
    elements.append(Spacer(1, 0.2*cm))
    
    # Separator line
    elements.append(Paragraph("_" * 80, header_style))
    elements.append(Spacer(1, 0.2*cm))
    
    # Customer and manager info - 2x2 table format
    created_at = order.created_at.strftime('%d.%m.%Y %H:%M')
    manager_name = order.manager.full_name if order.manager else "—"
    manager_phone = order.manager.phone if order.manager else "—"
    
    info_style = ParagraphStyle(
        'InfoText',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#333333'),
        spaceAfter=1,
        leading=10,
    )
    
    # Create 2x2 grid: top row = customer, bottom row = manager
    info_table = Table([
        [
            Paragraph(f"<b>Mijoz:</b> {order.user.full_name}", info_style),
            Paragraph(f"<b>Manager:</b> {manager_name}", info_style)
        ],
        [
            Paragraph(f"<b>Tel:</b> {order.user.phone}", info_style),
            Paragraph(f"<b>Tel:</b> {manager_phone}", info_style)
        ]
    ], colWidths=[4.5*cm, 4.5*cm])
    info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.2*cm))
    
    # Check number and date info
    check_info_style = ParagraphStyle(
        'CheckInfo',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#2196F3'),
        alignment=1,
        spaceAfter=4,
    )
    check_info = f"Chek #: {order.id}  |  Sana: {created_at}"
    elements.append(Paragraph(check_info, check_info_style))
    elements.append(Spacer(1, 0.2*cm))
    
    elements.append(Paragraph("_" * 80, header_style))
    elements.append(Spacer(1, 0.2*cm))
    
    # Items table with wider columns
    table_data = [
        ["#", "Mahsulot", "Birligi", "Miqdori", "Narxi (UZS)", "Jami (UZS)"]
    ]
    
    for i, item in enumerate(order.items, 1):
        table_data.append([
            str(i),
            f"{item.product.name[:18]}{_item_suffix(item)}",
            item.product.unit,
            f"{item.quantity:.2f}",
            f"{item.price:,.0f}",
            f"{item.total_price:,.0f}"
        ])
    
    # Add total row
    table_data.append([
        "", "", "", "", "JAMI:", f"{order.total_sum:,.0f}"
    ])
    
    # Add payment info row
    paid_amount = order.user.paid_sum if hasattr(order.user, 'paid_sum') else 0
    amount_due = order.user.total_purchase_sum - paid_amount if hasattr(order.user, 'total_purchase_sum') else 0
    table_data.append([
        "", "", "", "", "To'langan:", f"{paid_amount:,.0f}"
    ])
    table_data.append([
        "", "", "", "", "To'lanishi kerak:", f"{amount_due:,.0f}"
    ])
    
    # Wider column layout for better spacing
    table = Table(table_data, colWidths=[0.5*cm, 3.2*cm, 1.2*cm, 1.5*cm, 2.2*cm, 2.2*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('ALIGN', (4, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, -3), (-1, -1), colors.HexColor('#fff3e0')),
        ('FONTNAME', (0, -3), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -3), (-1, -1), 9),
        ('TOPPADDING', (0, -3), (-1, -1), 6),
        ('BOTTOMPADDING', (0, -3), (-1, -1), 6),
        ('BACKGROUND', (0, -3), (-1, -3), colors.HexColor('#f5f5f5')),  # Total row
        ('BACKGROUND', (0, -2), (-1, -2), colors.HexColor('#c8e6c9')),  # Paid row
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ffccbc')),  # Due row
        ('GRID', (0, 0), (-1, -1), 0.8, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -4), [colors.white, colors.HexColor('#fafafa')]),
        ('FONTSIZE', (0, 1), (-1, -4), 8),
        ('RIGHTPADDING', (4, 1), (-1, -1), 8),
        ('LEFTPADDING', (4, 1), (-1, -1), 8),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 0.3*cm))
    
    # Bottom separator
    elements.append(Paragraph("_" * 80, header_style))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_manager_report_pdf(manager, period_orders) -> BytesIO:
    """Generate manager daily/monthly report PDF"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.7*cm, bottomMargin=0.7*cm)
    
    styles, title_style, header_style = get_styles()
    elements = []
    
    # Company header
    company_header = Paragraph(
        "«NOVASTONE» FIRMA<br/>"
        "<font size='9'>Qurilish materiallari do'koni</font>",
        ParagraphStyle(
            'CompanyHeader',
            parent=styles['Normal'],
            fontSize=12,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#1a1a1a'),
            alignment=1,
            spaceAfter=8,
        )
    )
    elements.append(company_header)
    elements.append(Spacer(1, 0.2*cm))
    
    # Title
    title = Paragraph(
        f"📊 MANAGER HISOBOT",
        ParagraphStyle(
            'ReportTitle',
            parent=styles['Normal'],
            fontSize=12,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#2196F3'),
            alignment=1,
            spaceAfter=4,
        )
    )
    elements.append(title)
    
    # Manager name and date
    report_date = datetime.now(TZ).strftime('%d.%m.%Y %H:%M')
    manager_info = Paragraph(
        f"Manager: <b>{manager.full_name}</b><br/>Tayyorlash vaqti: {report_date}",
        header_style
    )
    elements.append(manager_info)
    elements.append(Spacer(1, 0.3*cm))
    
    # Group by customer
    customer_data = {}
    total_revenue = 0
    
    for order in period_orders:
        if order.user.id not in customer_data:
            customer_data[order.user.id] = {
                'user': order.user,
                'orders': [],
                'total': 0
            }
        customer_data[order.user.id]['orders'].append(order)
        customer_data[order.user.id]['total'] += order.total_sum
        total_revenue += order.total_sum
    
    # Customer summary table
    table_data = [
        ["Mijoz", "Telefon", "Buyurtmalar", "Jami Summa (UZS)", "To'langan (UZS)", "To'lanishi kerak (UZS)"]
    ]
    
    for cust_id, cust_info in customer_data.items():
        paid = cust_info['user'].paid_sum if hasattr(cust_info['user'], 'paid_sum') else 0
        due = cust_info['total'] - paid
        table_data.append([
            cust_info['user'].full_name,
            cust_info['user'].phone,
            str(len(cust_info['orders'])),
            f"{cust_info['total']:,.0f}",
            f"{paid:,.0f}",
            f"{due:,.0f}"
        ])
    
    # Total row (without <b> tags in data)
    total_paid = sum(
        (cust_info['user'].paid_sum if hasattr(cust_info['user'], 'paid_sum') else 0)
        for cust_info in customer_data.values()
    )
    total_due = total_revenue - total_paid
    
    table_data.append([
        "JAMI",
        "",
        str(len(period_orders)),
        f"{total_revenue:,.0f}",
        f"{total_paid:,.0f}",
        f"{total_due:,.0f}"
    ])
    
    table = Table(table_data, colWidths=[2.8*cm, 2.8*cm, 1.8*cm, 2.2*cm, 2.2*cm, 2.2*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2196F3')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#bbdefb')),
        ('BACKGROUND', (4, -1), (4, -1), colors.HexColor('#c8e6c9')),
        ('BACKGROUND', (5, -1), (5, -1), colors.HexColor('#ffccbc')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 9),
        ('TOPPADDING', (0, -1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.8, colors.HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#fafafa')]),
        ('FONTSIZE', (0, 1), (-1, -2), 8),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 0.4*cm))
    
    # Product-wise breakdown table
    product_data = {}
    for order in period_orders:
        for item in order.items:
            if item.product.id not in product_data:
                product_data[item.product.id] = {
                    'name': item.product.name,
                    'unit': item.product.unit,
                    'quantity': 0,
                    'total': 0
                }
            product_data[item.product.id]['quantity'] += item.quantity
            product_data[item.product.id]['total'] += item.total_price
    
    if product_data:
        elements.append(Paragraph(
            "<b>Mahsulot bo'yicha Hisobot:</b>",
            ParagraphStyle(
                'SectionTitle',
                parent=styles['Normal'],
                fontSize=9,
                fontName='Helvetica-Bold',
                textColor=colors.HexColor('#333333'),
                spaceAfter=4,
            )
        ))
        
        product_table_data = [
            ["Mahsulot", "Birligi", "Miqdori", "Summa (UZS)"]
        ]
        
        for prod_id, prod_info in sorted(product_data.items(), key=lambda x: x[1]['total'], reverse=True):
            product_table_data.append([
                prod_info['name'][:25],
                prod_info['unit'],
                f"{prod_info['quantity']:.2f}",
                f"{prod_info['total']:,.0f}"
            ])
        
        product_table = Table(product_table_data, colWidths=[4*cm, 1.5*cm, 1.8*cm, 2.7*cm])
        product_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4CAF50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
            ('TOPPADDING', (0, 0), (-1, 0), 4),
            ('GRID', (0, 0), (-1, -1), 0.8, colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fafafa')]),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        elements.append(product_table)
        elements.append(Spacer(1, 0.3*cm))
    
    # Summary section
    summary_style = ParagraphStyle(
        'Summary',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#333333'),
        spaceAfter=3,
        leading=14,
    )
    
    avg_order = total_revenue/len(period_orders) if period_orders else 0
    summary_text = f"""<b>Hisobot Xulosasi:</b><br/>
Jami Buyurtmalar: {len(period_orders)} ta<br/>
Jami Daromad: {total_revenue:,.0f} UZS<br/>
To'langan Summa: {total_paid:,.0f} UZS<br/>
To'lanishi kerak: {total_due:,.0f} UZS<br/>
O'rtacha Buyurtma: {avg_order:,.0f} UZS"""
    
    elements.append(Paragraph(summary_text, summary_style))
    elements.append(Spacer(1, 0.4*cm))
    
    # Footer
    footer_text = Paragraph(
        "«NOVASTONE» FIRMA<br/>"
        "<font size='9'><i>Raxmat!</i></font>",
        ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#666666'),
            alignment=1,
            spaceAfter=0,
        )
    )
    elements.append(footer_text)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_user_orders_pdf(user, user_orders_list) -> BytesIO:
    """Generate PDF with all user's orders summary and details"""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.7*cm, bottomMargin=0.7*cm)
    
    styles, title_style, header_style = get_styles()
    elements = []
    
    # Company header
    company_header = Paragraph(
        "«NOVASTONE» FIRMA<br/>"
        "<font size='9'>Qurilish materiallari do'koni</font>",
        ParagraphStyle(
            'CompanyHeader',
            parent=styles['Normal'],
            fontSize=12,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#1a1a1a'),
            alignment=1,
            spaceAfter=8,
        )
    )
    elements.append(company_header)
    elements.append(Spacer(1, 0.2*cm))
    
    # Title
    title = Paragraph(
        f"👤 MIJOZNING BUYURTMALARI",
        ParagraphStyle(
            'ReportTitle',
            parent=styles['Normal'],
            fontSize=12,
            fontName='Helvetica-Bold',
            textColor=colors.HexColor('#2196F3'),
            alignment=1,
            spaceAfter=4,
        )
    )
    elements.append(title)
    
    # Customer info
    report_date = datetime.now(TZ).strftime('%d.%m.%Y %H:%M')
    customer_info_style = ParagraphStyle(
        'CustomerInfo',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#333333'),
        spaceAfter=2,
    )
    
    customer_text = f"""<b>Mijoz:</b> {user.full_name}<br/>
<b>Telefon:</b> {user.phone}<br/>
<b>Ro'yxatdan o'tgan:</b> {user.created_at.strftime('%d.%m.%Y')}<br/>
<b>Hisobot tayyorlandi:</b> {report_date}"""
    
    elements.append(Paragraph(customer_text, customer_info_style))
    elements.append(Spacer(1, 0.3*cm))
    
    elements.append(Paragraph("_" * 80, header_style))
    elements.append(Spacer(1, 0.2*cm))
    total_orders = len(user_orders_list)
    total_sum = sum(order_info["order"].total_sum for order_info in user_orders_list)

    summary_table = Table([
        ["Jami buyurtmalar", str(total_orders), "Umumiy summa", f"{total_sum:,.0f} UZS"]
    ], colWidths=[3.0*cm, 1.6*cm, 3.0*cm, 2.4*cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#eaf4ff')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1a1a1a')),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.8, colors.HexColor('#90caf9')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('SPAN', (1, 0), (1, 0)),
        ('SPAN', (3, 0), (3, 0)),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.25*cm))

    section_style = ParagraphStyle(
        'OrderSection',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=4,
    )

    detail_style = ParagraphStyle(
        'OrderDetail',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#333333'),
        leading=10,
    )

    def item_label(item):
        category_name = (item.product.category.name if item.product and item.product.category else "").strip().lower()
        extra = item.size or ""
        if not extra:
            return ""
        if category_name == "travertin":
            return f"Rang: {extra}"
        if category_name == "tiya":
            return f"Razmer: {extra}"
        return extra

    for idx, order_info in enumerate(user_orders_list, 1):
        order = order_info["order"]
        order_date = order.created_at.strftime('%d.%m.%Y %H:%M')

        elements.append(Paragraph(f"{idx}. Buyurtma | Sana: {order_date}", section_style))
        elements.append(Paragraph(f"Buyurtma raqami: <b>#{order.id}</b>", detail_style))
        elements.append(Spacer(1, 0.12*cm))

        order_table_data = [["#", "Mahsulot", "Birligi", "Miqdori", "Qo'shimcha", "Narx", "Jami"]]
        for item_index, item in enumerate(order.items, 1):
            order_table_data.append([
                str(item_index),
                item.product.name[:20],
                item.product.unit,
                f"{item.quantity:.2f}",
                item_label(item),
                f"{item.price:,.0f}",
                f"{item.total_price:,.0f}",
            ])

        order_table_data.append(["", "", "", "", "Buyurtma jami", "", f"{order.total_sum:,.0f}"])

        order_table = Table(order_table_data, colWidths=[0.6*cm, 3.0*cm, 1.1*cm, 1.3*cm, 2.4*cm, 1.8*cm, 1.8*cm])
        order_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2196F3')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('ALIGN', (4, 0), (4, -1), 'LEFT'),
            ('ALIGN', (5, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
            ('TOPPADDING', (0, 0), (-1, 0), 5),
            ('GRID', (0, 0), (-1, -1), 0.7, colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#fafafa')]),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#bbdefb')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 8),
            ('TOPPADDING', (0, -1), (-1, -1), 5),
            ('BOTTOMPADDING', (0, -1), (-1, -1), 5),
        ]))

        elements.append(order_table)
        elements.append(Spacer(1, 0.18*cm))
        if idx < total_orders:
            elements.append(Paragraph("_" * 80, header_style))
            elements.append(Spacer(1, 0.18*cm))

    elements.append(Paragraph("_" * 80, header_style))
    elements.append(Spacer(1, 0.15*cm))

    paid_sum = user.paid_sum if hasattr(user, 'paid_sum') else 0
    amount_due = total_sum - paid_sum
    
    grand_total_table = Table([
        ["Jami buyurtmalar", str(total_orders)],
        ["Umumiy summa (UZS)", f"{total_sum:,.0f}"],
        ["To'langan (UZS)", f"{paid_sum:,.0f}"],
        ["To'lanishi kerak (UZS)", f"{amount_due:,.0f}"]
    ], colWidths=[4.5*cm, 3.5*cm])
    grand_total_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e3f2fd')),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#bbdefb')),
        ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#c8e6c9')),
        ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#ffccbc')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1a1a1a')),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.8, colors.HexColor('#cccccc')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BACKGROUND', (0, 0), (0, 3), colors.HexColor('#f5faff')),
    ]))
    elements.append(grand_total_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer
