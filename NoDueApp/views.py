from transformers import AutoTokenizer, RagRetriever
import torch
from django.shortcuts import render
from django.template import RequestContext
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
import os
import pickle
import pymysql
from django.core.files.storage import FileSystemStorage
import io
import base64
import numpy as np
import matplotlib.pyplot as plt
import smtplib
import pandas as pd
from datetime import date, datetime
import random
from matplotlib.backends.backend_pdf import PdfPages
import hashlib
import numpy as np
from numpy import dot
from numpy.linalg import norm
import os
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import qrcode
from PIL import Image as PILImage
import zipfile

global uname, dept, df, cleared, student_year, student_name_global, student_course_global

# Initialize global variables
uname = ""
dept = ""
df = []
cleared = "no"
student_year = ""
student_name_global = ""
student_course_global = ""

global tokenizer, retriever, model
tokenizer = AutoTokenizer.from_pretrained("facebook/rag-sequence-nq")
model = RagRetriever.from_pretrained("facebook/rag-sequence-nq", index_name="exact", use_dummy_dataset=True)
#model = RagSequenceForGeneration.from_pretrained("facebook/rag-token-nq", retriever=retriever)

def sendEmail(email, msg):
    em = []
    em.append(email)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as connection:
        email_address = 'kaleem202120@gmail.com'
        email_password = 'xyljzncebdxcubjq'
        connection.login(email_address, email_password)
        connection.sendmail(from_addr="kaleem202120@gmail.com", to_addrs=em, msg=msg)

def getMail(student):
    email = ""
    con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
    with con:
        cur = con.cursor()
        cur.execute("select email from student where student_id='"+student+"'")
        rows = cur.fetchall()
        for row in rows:
            email = row[0]
            break
    sendEmail(email, "Your no due certificate generated and can be downloaded by login to appplication")    

def getTotalFee(student, year):
    library = 0
    hostel = 0
    tution = 0
    exam = 0
    lab = 0
    con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
    with con:
        cur = con.cursor()
        cur.execute("select library_fee,hostel_fee,tution_fee,exam_fee,lab_hod_fee from student where student_id='"+student+"' and course_year='"+year+"'")
        rows = cur.fetchall()
        for row in rows:
            library = row[0] if row[0] is not None else 0
            hostel = row[1] if row[1] is not None else 0
            tution = row[2] if row[2] is not None else 0
            exam = row[3] if row[3] is not None else 0
            lab = row[4] if row[4] is not None else 0
            break
    return library, hostel, tution, exam, lab

def getPaidFee(student, year):
    library = 0
    hostel = 0
    tution = 0
    exam = 0
    lab = 0
    con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
    with con:
        cur = con.cursor()
        cur.execute("select sum(amount) from payments where paying_dept='Accounts' and student_id='"+student+"' and course_year='"+year+"'")
        rows = cur.fetchall()
        for row in rows:
            tution = row[0]
            break
    con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
    with con:
        cur = con.cursor()
        cur.execute("select sum(amount) from payments where paying_dept='Library' and student_id='"+student+"' and course_year='"+year+"'")
        rows = cur.fetchall()
        for row in rows:
            library = row[0]
            break
    con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
    with con:
        cur = con.cursor()
        cur.execute("select sum(amount) from payments where paying_dept='Hostel' and student_id='"+student+"' and course_year='"+year+"'")
        rows = cur.fetchall()
        for row in rows:
            hostel = row[0]
            break
    con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
    with con:
        cur = con.cursor()
        cur.execute("select sum(amount) from payments where paying_dept='Exam Fee Dept' and student_id='"+student+"' and course_year='"+year+"'")
        rows = cur.fetchall()
        for row in rows:
            exam = row[0]
            break
    con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
    with con:
        cur = con.cursor()
        cur.execute("select sum(amount) from payments where paying_dept='HOD Lab Returns' and student_id='"+student+"' and course_year='"+year+"'")
        rows = cur.fetchall()
        for row in rows:
            lab = row[0]
            break
    if tution is None:
        tution = 0
    if library is None:
        library = 0
    if exam is None:
        exam = 0
    if hostel is None:
        hostel = 0
    if lab is None:
        lab = 0    
    return library, hostel, tution, exam, lab

def getDepartmentTotalFee(student, year, department):
    """Get total fee for a specific department"""
    total_library, total_hostel, total_tution, total_exam, total_lab = getTotalFee(student, year)
    
    # Convert to float and handle None values
    if department == "Accounts":
        return float(total_tution) if total_tution is not None and total_tution != 0 else 0.0
    elif department == "Library":
        return float(total_library) if total_library is not None and total_library != 0 else 0.0
    elif department == "Hostel":
        return float(total_hostel) if total_hostel is not None and total_hostel != 0 else 0.0
    elif department == "Exam Fee Dept":
        return float(total_exam) if total_exam is not None and total_exam != 0 else 0.0
    elif department == "HOD Lab Returns":
        return float(total_lab) if total_lab is not None and total_lab != 0 else 0.0
    return 0.0

def getCumulativePaidAmount(student, year, department, payment_date):
    """Get cumulative paid amount for a department up to a specific payment date"""
    cumulative_paid = 0
    try:
        con = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='root', database='nodue', charset='utf8')
        with con:
            cur = con.cursor()
            # Get sum of payments for this department up to and including the payment date
            query = "SELECT COALESCE(SUM(amount), 0) FROM payments WHERE student_id=%s AND course_year=%s AND paying_dept=%s AND payment_date <= %s"
            cur.execute(query, (student, year, department, payment_date))
            row = cur.fetchone()
            if row and row[0] is not None:
                cumulative_paid = float(row[0])
    except Exception as e:
        print(f"Error calculating cumulative paid amount: {e}")
    return cumulative_paid

def getStudentDetails(student_id, year):
    """Get student name and course details from database"""
    student_name = ""
    course = ""
    con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
    with con:
        cur = con.cursor()
        cur.execute("select student_name, course from student where student_id='"+student_id+"' and course_year='"+year+"'")
        rows = cur.fetchall()
        for row in rows:
            student_name = row[0] if row[0] else ""
            course = row[1] if row[1] else ""
            break
    return student_name, course

def add_border(canvas, doc):
    """Add decorative border to the certificate"""
    canvas.saveState()
    # Outer border
    canvas.setStrokeColor(HexColor('#1a237e'))
    canvas.setLineWidth(3)
    canvas.rect(0.5*inch, 0.5*inch, A4[0]-1*inch, A4[1]-1*inch)
    # Inner decorative border
    canvas.setStrokeColor(HexColor('#283593'))
    canvas.setLineWidth(1)
    canvas.rect(0.6*inch, 0.6*inch, A4[0]-1.2*inch, A4[1]-1.2*inch)
    canvas.restoreState()

def getCertificate(student_id, student_name, course, year, fee_data):
    """Generate a professional No Due Certificate PDF"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                            rightMargin=0.75*inch, leftMargin=0.75*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch,
                            onFirstPage=add_border, onLaterPages=add_border)
    
    # Get the path to the logo image
    current_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(current_dir, 'static', 'logo_red.png')
    
    # Container for the 'Flowable' objects
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=HexColor('#1a237e'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=18,
        textColor=HexColor('#283593'),
        spaceAfter=20,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=12,
        textColor=HexColor('#000000'),
        spaceAfter=12,
        alignment=TA_LEFT,
        fontName='Helvetica'
    )
    
    center_style = ParagraphStyle(
        'CenterStyle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=HexColor('#000000'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica'
    )
    
    # College Logo
    elements.append(Spacer(1, 0.3*inch))
    logo_loaded = False
    
    # Try primary logo path
    if os.path.exists(logo_path):
        try:
            logo = RLImage(logo_path, width=3*inch, height=1*inch, kind='proportional')
            logo_table = Table([[logo]], colWidths=[A4[0] - 1.5*inch])
            logo_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(logo_table)
            elements.append(Spacer(1, 0.3*inch))
            logo_loaded = True
        except Exception as e:
            # Try alternative path if primary fails
            alt_logo_path = os.path.join(current_dir, 'static', 'css', 'logo_red.png')
            if os.path.exists(alt_logo_path):
                try:
                    logo = RLImage(alt_logo_path, width=3*inch, height=1*inch, kind='proportional')
                    logo_table = Table([[logo]], colWidths=[A4[0] - 1.5*inch])
                    logo_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ]))
                    elements.append(logo_table)
                    elements.append(Spacer(1, 0.3*inch))
                    logo_loaded = True
                except:
                    pass
    
    # If primary path doesn't exist, try alternative path
    if not logo_loaded:
        alt_logo_path = os.path.join(current_dir, 'static', 'css', 'logo_red.png')
        if os.path.exists(alt_logo_path):
            try:
                logo = RLImage(alt_logo_path, width=3*inch, height=1*inch, kind='proportional')
                logo_table = Table([[logo]], colWidths=[A4[0] - 1.5*inch])
                logo_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                elements.append(logo_table)
                elements.append(Spacer(1, 0.3*inch))
                logo_loaded = True
            except:
                pass
    
    # Final attempt with primary path even if it didn't exist before
    if not logo_loaded:
        try:
            logo = RLImage(logo_path, width=3*inch, height=1*inch, kind='proportional')
            logo_table = Table([[logo]], colWidths=[A4[0] - 1.5*inch])
            logo_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            elements.append(logo_table)
            elements.append(Spacer(1, 0.3*inch))
        except:
            pass
    
    # Certificate Title
    title = Paragraph("NO DUE CERTIFICATE", title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.3*inch))
    
    # Certificate Body
    student_display_name = student_name if student_name else f"Student ID: {student_id}"
    course_display = course if course else "the course"
    
    cert_text = f"This is to certify that <b>{student_display_name}</b> (Student ID: <b>{student_id}</b>), " \
                f"pursuing <b>{course_display}</b> in the academic year <b>{year}</b>, has cleared all dues " \
                f"pertaining to the following departments:"
    
    cert_para = Paragraph(cert_text, body_style)
    elements.append(cert_para)
    elements.append(Spacer(1, 0.2*inch))
    
    # Fee Details Table
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.whitesmoke,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    USE_RUPEE_SYMBOL = False  # Set to True to use ₹ symbol
    
    if USE_RUPEE_SYMBOL:
        rupee_char = '₹'  # Unicode U+20B9
        total_header = f'Total Fee ({rupee_char})'
        paid_header = f'Paid Fee ({rupee_char})'
    else:
        # Using 'Rs.' which is universally supported
        total_header = 'Total Fee (Rs.)'
        paid_header = 'Paid Fee (Rs.)'
    
    table_data = [[
        Paragraph('Fee Type', header_style),
        Paragraph(total_header, header_style),
        Paragraph(paid_header, header_style),
        Paragraph('Status', header_style)
    ]]
    
    for row in fee_data[1:]:  # Skip the first row (Student ID row)
        fee_type = str(row[0])
        total_fee = str(row[1]) if len(row) > 1 else "0"
        paid_fee = str(row[2]) if len(row) > 2 else "0"
        status = str(row[3]) if len(row) > 3 else "N/A"
        
        # Format status with color indication
        if status == "Cleared":
            status_text = f'<font color="green"><b>{status}</b></font>'
        else:
            status_text = f'<font color="red"><b>{status}</b></font>'
        
        table_data.append([
            Paragraph(fee_type, body_style),
            Paragraph(total_fee, center_style),
            Paragraph(paid_fee, center_style),
            Paragraph(status_text, center_style)
        ])
    
    # Create table
    fee_table = Table(table_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
    fee_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1a237e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), HexColor('#e8eaf6')),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
    ]))
    
    elements.append(fee_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Declaration
    declaration = Paragraph(
        "This certificate is issued on the basis that all dues have been cleared and verified by the respective departments.",
        body_style
    )
    elements.append(declaration)
    elements.append(Spacer(1, 0.4*inch))
    
    # Certificate Number and Date
    cert_hash = hashlib.sha256((student_id + " No Due Certificate " + year).encode()).hexdigest()[:15]
    cert_date = datetime.now().strftime("%d %B %Y")
    
    cert_info = Paragraph(
        f"<b>Certificate No:</b> {cert_hash}<br/>"
        f"<b>Date of Issue:</b> {cert_date}",
        body_style
    )
    elements.append(cert_info)
    elements.append(Spacer(1, 0.5*inch))
    
    # Signatures section
    signature_data = [
        ['', '', ''],
        ['_________________', '_________________', '_________________'],
        ['Accounts Department', 'Library Department', 'Hostel Department'],
        ['', '', ''],
        ['_________________', '_________________', ''],
        ['Exam Fee Department', 'HOD Lab Returns', ''],
        ['', '', ''],
        ['', '', '_________________'],
        ['', '', 'Registrar/Principal']
    ]
    
    sig_table = Table(signature_data, colWidths=[2.5*inch, 2.5*inch, 2.5*inch])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica'),
        ('FONTNAME', (0, 2), (-1, 2), 'Helvetica'),
        ('FONTNAME', (0, 4), (-1, 4), 'Helvetica'),
        ('FONTNAME', (0, 5), (-1, 5), 'Helvetica'),
        ('FONTNAME', (0, 8), (-1, 8), 'Helvetica-Bold'),
    ]))
    
    elements.append(sig_table)
    
    # Build PDF
    doc.build(elements)
    
    # Get the value of the BytesIO buffer
    pdf_data = buffer.getvalue()
    buffer.close()
    
    name = f"{student_id}_no_due_certificate.pdf"
    return name, pdf_data

def Download(request):
    if request.method == 'GET':
        global uname, dept, df, cleared, student_year, student_name_global, student_course_global
        download_type = request.GET.get('type', 'certificate')  # 'certificate', 'qr', or 'both'
        
        if cleared == "yes":
            # Get student details if not already stored
            try:
                if not student_name_global or not student_course_global or not student_year:
                    student_name_global, student_course_global = getStudentDetails(uname, student_year)
            except:
                student_name_global, student_course_global = getStudentDetails(uname, student_year)
            
            # Certificate Number and Date for QR code
            cert_hash = hashlib.sha256((uname + " No Due Certificate " + student_year).encode()).hexdigest()[:15]
            cert_date = datetime.now().strftime("%d %B %Y")
            
            # Generate QR code data
            qr_data = f"Student ID: {uname}\nYear: {student_year}\nCertificate No: {cert_hash}\nDate: {cert_date}\nStatus: Verified"
            
            if download_type == 'qr':
                # Download QR code only
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=10,
                    border=4,
                )
                qr.add_data(qr_data)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white")
                
                # Save QR code to BytesIO
                qr_buffer = io.BytesIO()
                qr_img.save(qr_buffer, format='PNG')
                qr_buffer.seek(0)
                
                response = HttpResponse(qr_buffer.getvalue(), content_type='image/png')
                response['Content-Disposition'] = f'attachment; filename={uname}_qr_code.png'
                return response
                
            elif download_type == 'both':
                # Download both as ZIP
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    # Add PDF certificate
                    pdf_name, pdf_data = getCertificate(uname, student_name_global, student_course_global, student_year, df)
                    zip_file.writestr(pdf_name, pdf_data)
                    
                    # Add QR code image
                    qr = qrcode.QRCode(
                        version=1,
                        error_correction=qrcode.constants.ERROR_CORRECT_L,
                        box_size=10,
                        border=4,
                    )
                    qr.add_data(qr_data)
                    qr.make(fit=True)
                    qr_img = qr.make_image(fill_color="black", back_color="white")
                    
                    qr_buffer = io.BytesIO()
                    qr_img.save(qr_buffer, format='PNG')
                    qr_buffer.seek(0)
                    zip_file.writestr(f'{uname}_qr_code.png', qr_buffer.getvalue())
                
                zip_buffer.seek(0)
                response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
                response['Content-Disposition'] = f'attachment; filename={uname}_no_due_certificate_and_qr.zip'
                return response
                
            else:
                # Download certificate only (default)
                name, data = getCertificate(uname, student_name_global, student_course_global, student_year, df)
                response = HttpResponse(data, content_type='application/pdf')
                response['Content-Disposition'] = 'attachment; filename='+name
                return response
        else:
            output = "<font size=3 color=red>Due is NOT Cleared</font>"
            context= {'data':output}
            return render(request,'StudentScreen.html', context) 

def GenerateNoDueAction(request):
    if request.method == 'POST':
        global uname, dept, df, cleared, student_year, student_name_global, student_course_global
        student = request.POST.get('t1', False)
        year = request.POST.get('t2', False)
        student_year = year
        # Get student details
        student_name_global, student_course_global = getStudentDetails(student, year)
        inputs = tokenizer(student+" "+year, return_tensors="pt")
        input_ids = inputs["input_ids"]
        #due_detect = model.question_encoder(input_ids)[0]
        output = '<font size=3 color=black>Student Id = '+student+"</font><br/>"
        output += '<font size=3 color=black>Course Year = '+year+"</font><br/><br/>"
        output+='<table border=1 align=center width=100%><tr><th><font size="3" color="black">Fee Type</th><th><font size="3" color="black">Total Fee</th>'
        output+='<th><font size="3" color="black">Paid Fee</th><th><font size="3" color="black">Due Status</th></tr>'
        total_library, total_hostel, total_tution, total_exam, total_lab = getTotalFee(student, year)
        paid_library, paid_hostel, paid_tution, paid_exam, paid_lab = getPaidFee(student, year)
        status = "none"
        df = []
        signed = student+" No Due Certificate"
        df.append(["Student Id", student, "Year : "+year, "Signed : "+hashlib.sha256(signed.encode()).hexdigest()[0:15]])
        # Check if at least one fee structure exists (including 0 fees)
        if total_library is not None or total_hostel is not None or total_tution is not None or total_exam is not None or total_lab is not None:
            # Tution Fee
            output+='<tr><td><font size="3" color="black">Tution Fee</td><td><font size="3" color="black">'+str(total_tution)+'</td><td><font size="3" color="black">'+str(paid_tution)+'</td>' 
            # If total fee is 0, it's automatically cleared
            if total_tution == 0 or (total_tution > 0 and paid_tution >= total_tution):
                output+='<td><font size="3" color="Green">Cleared</td></tr>'
                signed = "Cleared"
            else:
                output+='<td><font size="3" color="red">Not Cleared</td></tr>'
                status = "Pending"
                signed = "Not Cleared"
            df.append(["Tution Fee", total_tution, paid_tution, signed])    
            
            # Library Fee
            output+='<tr><td><font size="3" color="black">Library Fee</td><td><font size="3" color="black">'+str(total_library)+'</td><td><font size="3" color="black">'+str(paid_library)+'</td>' 
            # If total fee is 0, it's automatically cleared
            if total_library == 0 or (total_library > 0 and paid_library >= total_library):
                output+='<td><font size="3" color="Green">Cleared</td></tr>'
                signed = "Cleared"
            else:
                output+='<td><font size="3" color="red">Not Cleared</td></tr>'
                status = "Pending"
                signed = "Not Cleared"
            df.append(["Library Fee", total_library, paid_library, signed])     
            
            # Hostel Fee
            output+='<tr><td><font size="3" color="black">Hostel Fee</td><td><font size="3" color="black">'+str(total_hostel)+'</td><td><font size="3" color="black">'+str(paid_hostel)+'</td>' 
            # If total fee is 0, it's automatically cleared
            if total_hostel == 0 or (total_hostel > 0 and paid_hostel >= total_hostel):
                output+='<td><font size="3" color="Green">Cleared</td></tr>'
                signed = "Cleared"
            else:
                status = "Pending"
                signed = "Not Cleared"
                output+='<td><font size="3" color="red">Not Cleared</td></tr>'
            df.append(["Hostel Fee", total_hostel, paid_hostel, signed]) 
            
            # Exam Fee
            output+='<tr><td><font size="3" color="black">Exam Fee</td><td><font size="3" color="black">'+str(total_exam)+'</td><td><font size="3" color="black">'+str(paid_exam)+'</td>' 
            # If total fee is 0, it's automatically cleared
            if total_exam == 0 or (total_exam > 0 and paid_exam >= total_exam):
                signed = "Cleared"
                output+='<td><font size="3" color="Green">Cleared</td></tr>'
            else:
                status = "Pending"
                signed = "Not Cleared"
                output+='<td><font size="3" color="red">Not Cleared</td></tr>'
            df.append(["Exam Fee", total_exam, paid_exam, signed])     
            
            # Lab Returns HOD Fee
            output+='<tr><td><font size="3" color="black">Lab Returns HOD Fee</td><td><font size="3" color="black">'+str(total_lab)+'</td><td><font size="3" color="black">'+str(paid_lab)+'</td>' 
            # If total fee is 0, it's automatically cleared
            if total_lab == 0 or (total_lab > 0 and paid_lab >= total_lab):
                signed = "Cleared"
                output+='<td><font size="3" color="Green">Cleared</td></tr>'
            else:
                status = "Pending"
                signed = "Not Cleared"
                output+='<td><font size="3" color="red">Not Cleared</td></tr>'
            df.append(["Lab Returns HOD Fee",total_lab, paid_lab, signed])
            
            if status == "none":
                cleared = "yes"
                getMail(uname)
            else:
                cleared = "no"
        else:
            output = '<font size=3 color=red>No Fee Structure Found</font><br/>'
            cleared = "no"
        context= {'data':output}
        return render(request, 'StudentScreen.html', context)
    else:
        # uname is already declared as global at the top of this function
        student_id_value = uname if uname else ''
        return render(request, 'GenerateNoDue.html', {'student_id': student_id_value, 'data': '<div class="alert-message error"><i class="fa fa-exclamation-circle"></i> Invalid request method. Please use the form to generate certificate.</div>'})

def GenerateNoDue(request):
    if request.method == 'GET':
        global uname
        context = {'student_id': uname if uname else ''}
        return render(request, 'GenerateNoDue.html', context)        

def ViewStudents(request):
    if request.method == 'GET':
        global dept
        students = []
        con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
        with con:
            cur = con.cursor()
            cur.execute("select * from student")
            rows = cur.fetchall()
            for row in rows:
                students.append(row)
        # Determine dashboard based on user type (employee has dept set)
        dashboard_link = '/EmployeeScreen.html' if dept else '/AdminScreen.html'
        context = {'students': students, 'data': '', 'dashboard_link': dashboard_link}
        return render(request, 'ViewStudents.html', context) 

def AcceptFeeAction(request):
    if request.method == 'POST':
        global uname, dept
        student = request.POST.get('t1', False)
        fee = request.POST.get('t2', False)
        year = request.POST.get('t3', False)
        
        # Validate required fields
        if not student or not fee or not year:
            status = "<div class='alert-message error'><i class='fa fa-exclamation-circle'></i> All fields are required. Please fill in Student ID, Fee Amount, and Course Year.</div>"
            context = {'data': status}
            return render(request, 'EmployeeScreen.html', context)
        
        # Validate fee is numeric and positive
        try:
            fee_value = float(fee)
            if fee_value < 0:
                status = "<div class='alert-message error'><i class='fa fa-exclamation-circle'></i> Fee amount cannot be negative.</div>"
                context = {'data': status}
                return render(request, 'EmployeeScreen.html', context)
        except ValueError:
            status = "<div class='alert-message error'><i class='fa fa-exclamation-circle'></i> Invalid fee amount. Please enter a valid number.</div>"
            context = {'data': status}
            return render(request, 'EmployeeScreen.html', context)
        
        # Verify that student_id and course_year combination exists in the student table
        try:
            db_connection = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='root', database='nodue', charset='utf8')
            try:
                db_cursor = db_connection.cursor()
                # Check if student exists with the given course_year
                check_query = "SELECT student_id FROM student WHERE student_id = %s AND course_year = %s"
                db_cursor.execute(check_query, (student, year))
                student_record = db_cursor.fetchone()
                
                if not student_record:
                    status = "<div class='alert-message error'><i class='fa fa-exclamation-circle'></i> Student ID <strong>" + str(student) + "</strong> with Course Year <strong>" + str(year) + "</strong> not found. Please verify the details.</div>"
                    context = {'data': status}
                    db_cursor.close()
                    db_connection.close()
                    return render(request, 'EmployeeScreen.html', context)
                
                # Check if the department fee is 0 for this student (no due)
                department_total_fee = getDepartmentTotalFee(student, year, dept)
                if department_total_fee == 0:
                    status = "<div class='alert-message info'><i class='fa fa-info-circle'></i> <strong>No Due</strong> for Student ID <strong>" + str(student) + "</strong> with Course Year <strong>" + str(year) + "</strong> in <strong>" + dept + "</strong> department. Fee amount is ₹0.</div>"
                    context = {'data': status}
                    db_cursor.close()
                    db_connection.close()
                    return render(request, 'EmployeeScreen.html', context)
                
                # If student exists and has a due, proceed with payment insertion
                dd = str(date.today())
                insert_query = "INSERT INTO payments VALUES(%s, %s, %s, %s, %s)"
                db_cursor.execute(insert_query, (student, year, dept, fee_value, dd))
                db_connection.commit()
                
                if db_cursor.rowcount == 1:
                    status = "<div class='alert-message success'><i class='fa fa-check-circle'></i> <strong>"+dept+"</strong> fee of ₹"+str(fee_value)+" successfully accepted from student <strong>"+student+"</strong> for Course Year <strong>"+year+"</strong></div>"
                else:
                    status = "<div class='alert-message error'><i class='fa fa-exclamation-circle'></i> Failed to record payment. Please try again.</div>"
                    
            except pymysql.Error as e:
                db_connection.rollback()
                status = "<div class='alert-message error'><i class='fa fa-exclamation-circle'></i> Database error occurred: " + str(e) + "</div>"
            finally:
                db_cursor.close()
                db_connection.close()
        except pymysql.Error as e:
            status = "<div class='alert-message error'><i class='fa fa-exclamation-circle'></i> Database connection error: " + str(e) + "</div>"
        except Exception as e:
            status = "<div class='alert-message error'><i class='fa fa-exclamation-circle'></i> An unexpected error occurred: " + str(e) + "</div>"
        
        context = {'data': status}
        return render(request, 'EmployeeScreen.html', context)
    else:
        students = []
        con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
        with con:
            cur = con.cursor()
            cur.execute("select student_id from student")
            rows = cur.fetchall()
            for row in rows:
                students.append(row[0])
        return render(request, 'AcceptFee.html', {'students': students, 'dept': dept if 'dept' in globals() else '', 'fee_type': '', 'fee_label': '', 'data': '<font size=3 color=red>Invalid request method. Please use the form to accept fee.</font>'})

def AcceptFee(request):
    if request.method == 'GET':
        global dept
        students = []
        con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
        with con:
            cur = con.cursor()
            cur.execute("select student_id from student")
            rows = cur.fetchall()
            for row in rows:
                students.append(row[0])
        
        # Determine fee type based on department
        fee_type = ""
        fee_label = ""
        if dept == "Accounts":
            fee_type = "tution_fee"
            fee_label = "Tution Fee"
        elif dept == "Library":
            fee_type = "library_fee"
            fee_label = "Library Fee"
        elif dept == "Hostel":
            fee_type = "hostel_fee"
            fee_label = "Hostel Fee"
        elif dept == "Exam Fee Dept":
            fee_type = "exam_fee"
            fee_label = "Exam Fee"
        elif dept == "HOD Lab Returns":
            fee_type = "lab_hod_fee"
            fee_label = "Lab Returns HOD Fee"
        
        context = {
            'students': students,
            'dept': dept,
            'fee_type': fee_type,
            'fee_label': fee_label
        }
        return render(request, 'AcceptFee.html', context)

def UpdateFeeAction(request):
    if request.method == 'POST':
        global uname, dept
        student = request.POST.get('t1', False)
        fee = request.POST.get('t2', False)
        year = request.POST.get('t3', False)
        
        # Validate required fields
        if not student or not fee or not year:
            status = "<div class='alert-message error'><i class='fa fa-exclamation-circle'></i> All fields are required. Please fill in all the details.</div>"
            context = {'data': status}
            return render(request, 'EmployeeScreen.html', context)
        
        # Validate fee is numeric (allow 0 as valid value)
        try:
            fee_value = float(fee)
            if fee_value < 0:
                status = "<div class='alert-message error'><i class='fa fa-exclamation-circle'></i> Fee amount cannot be negative.</div>"
                context = {'data': status}
                return render(request, 'EmployeeScreen.html', context)
            # Note: fee_value can be 0, which means the fee is cleared/waved
        except ValueError:
            status = "<div class='alert-message error'><i class='fa fa-exclamation-circle'></i> Invalid fee amount. Please enter a valid number.</div>"
            context = {'data': status}
            return render(request, 'EmployeeScreen.html', context)
        
        # Determine column based on department
        column = ""
        if dept == "Accounts":
            column = 'tution_fee'
        elif dept == "Library":
            column = 'library_fee'
        elif dept == "Hostel":
            column = 'hostel_fee'
        elif dept == "Exam Fee Dept":
            column = 'exam_fee'
        elif dept == "HOD Lab Returns":
            column = 'lab_hod_fee'
        
        # Check if column was determined
        if not column:
            status = "<div class='alert-message error'><i class='fa fa-exclamation-circle'></i> Invalid department. Cannot determine fee type to update.</div>"
            context = {'data': status}
            return render(request, 'EmployeeScreen.html', context)
        
        # Execute database update with proper error handling
        try:
            db_connection = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='root', database='nodue', charset='utf8')
            try:
                db_cursor = db_connection.cursor()
                # Use parameterized query to prevent SQL injection
                query = "UPDATE student SET " + column + " = %s WHERE student_id = %s AND course_year = %s"
                db_cursor.execute(query, (fee_value, student, year))
                db_connection.commit()
                
                if db_cursor.rowcount == 1:
                    status = "<div class='alert-message success'><i class='fa fa-check-circle'></i> Selected student fee successfully updated</div>"
                elif db_cursor.rowcount == 0:
                    status = "<div class='alert-message error'><i class='fa fa-exclamation-circle'></i> No student found with Student ID: " + str(student) + " and Course Year: " + str(year) + ". Please verify the details.</div>"
                else:
                    status = "<div class='alert-message error'><i class='fa fa-exclamation-circle'></i> Unexpected error: Multiple records updated. Please contact administrator.</div>"
            except pymysql.Error as e:
                db_connection.rollback()
                status = "<div class='alert-message error'><i class='fa fa-exclamation-circle'></i> Database error occurred: " + str(e) + "</div>"
            finally:
                db_cursor.close()
                db_connection.close()
        except pymysql.Error as e:
            status = "<div class='alert-message error'><i class='fa fa-exclamation-circle'></i> Database connection error: " + str(e) + "</div>"
        except Exception as e:
            status = "<div class='alert-message error'><i class='fa fa-exclamation-circle'></i> An unexpected error occurred: " + str(e) + "</div>"
        
        context = {'data': status}
        return render(request, 'EmployeeScreen.html', context)
    else:
        students = []
        con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
        with con:
            cur = con.cursor()
            cur.execute("select student_id from student")
            rows = cur.fetchall()
            for row in rows:
                students.append(row[0])
        return render(request, 'UpdateFee.html', {'students': students, 'dept': dept if 'dept' in globals() else '', 'fee_type': '', 'fee_label': '', 'data': '<font size=3 color=red>Invalid request method. Please use the form to update fee.</font>'})

def UpdateFee(request):
    if request.method == 'GET':
        global dept
        students = []
        con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
        with con:
            cur = con.cursor()
            cur.execute("select student_id from student")
            rows = cur.fetchall()
            for row in rows:
                students.append(row[0])
        
        # Determine fee type based on department
        fee_type = ""
        fee_label = ""
        if dept == "Accounts":
            fee_type = "tution_fee"
            fee_label = "Tution Fee"
        elif dept == "Library":
            fee_type = "library_fee"
            fee_label = "Library Fee"
        elif dept == "Hostel":
            fee_type = "hostel_fee"
            fee_label = "Hostel Fee"
        elif dept == "Exam Fee Dept":
            fee_type = "exam_fee"
            fee_label = "Exam Fee"
        elif dept == "HOD Lab Returns":
            fee_type = "lab_hod_fee"
            fee_label = "Lab Returns HOD Fee"
        
        context = {
            'students': students,
            'dept': dept,
            'fee_type': fee_type,
            'fee_label': fee_label
        }
        return render(request, 'UpdateFee.html', context)

def EmployeeLogin(request):
    if request.method == 'GET':
       return render(request, 'EmployeeLogin.html', {})

def AdminLogin(request):
    if request.method == 'GET':
       return render(request, 'AdminLogin.html', {})    

def StudentLogin(request):
    if request.method == 'GET':
       return render(request, 'StudentLogin.html', {})

def AddEmployee(request):
    if request.method == 'GET':
       return render(request, 'AddEmployee.html', {})

def AddStudent(request):
    if request.method == 'GET':
       return render(request, 'AddStudent.html', {})    

def index(request):
    if request.method == 'GET':
        return render(request, 'index.html', {})

def ScanQR(request):
    if request.method == 'GET':
        return render(request, 'ScanQR.html', {})

def VerifyCertificate(request):
    if request.method == 'GET':
        student_id = request.GET.get('student_id', '')
        year = request.GET.get('year', '')
        
        if not student_id or not year:
            return JsonResponse({'success': False, 'message': 'Student ID and Year are required'})
        
        try:
            # Get student details
            student_name, course = getStudentDetails(student_id, year)
            
            # Check if student exists and has cleared dues
            con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
            with con:
                cur = con.cursor()
                cur.execute("select * from student where student_id='"+student_id+"' and course_year='"+year+"'")
                student = cur.fetchone()
                
                if not student:
                    return JsonResponse({'success': False, 'message': 'Student not found'})
                
                # Check if all fees are cleared
                total_library, total_hostel, total_tution, total_exam, total_lab = getTotalFee(student_id, year)
                paid_library, paid_hostel, paid_tution, paid_exam, paid_lab = getPaidFee(student_id, year)
                
                all_cleared = (
                    (total_tution == 0 or paid_tution >= total_tution) and
                    (total_library == 0 or paid_library >= total_library) and
                    (total_hostel == 0 or paid_hostel >= total_hostel) and
                    (total_exam == 0 or paid_exam >= total_exam) and
                    (total_lab == 0 or paid_lab >= total_lab)
                )
                
                if all_cleared:
                    return JsonResponse({
                        'success': True,
                        'student_name': student_name,
                        'course': course,
                        'message': 'Certificate is valid'
                    })
                else:
                    return JsonResponse({'success': False, 'message': 'Student has pending dues'})
                    
        except Exception as e:
            return JsonResponse({'success': False, 'message': 'Error verifying certificate: ' + str(e)})

def DownloadByQR(request):
    if request.method == 'GET':
        student_id = request.GET.get('student_id', '')
        year = request.GET.get('year', '')
        
        if not student_id or not year:
            return HttpResponse('Student ID and Year are required', status=400)
        
        try:
            # Get student details
            student_name, course = getStudentDetails(student_id, year)
            
            # Get fee data
            total_library, total_hostel, total_tution, total_exam, total_lab = getTotalFee(student_id, year)
            paid_library, paid_hostel, paid_tution, paid_exam, paid_lab = getPaidFee(student_id, year)
            
            # Build fee data array
            df = []
            signed = student_id + " No Due Certificate"
            df.append(["Student Id", student_id, "Year : " + year, "Signed : " + hashlib.sha256(signed.encode()).hexdigest()[:15]])
            
            if total_tution != 0:
                df.append(["Tution Fee", total_tution, paid_tution, "Cleared" if paid_tution >= total_tution else "Not Cleared"])
            if total_library != 0:
                df.append(["Library Fee", total_library, paid_library, "Cleared" if paid_library >= total_library else "Not Cleared"])
            if total_hostel != 0:
                df.append(["Hostel Fee", total_hostel, paid_hostel, "Cleared" if paid_hostel >= total_hostel else "Not Cleared"])
            if total_exam != 0:
                df.append(["Exam Fee", total_exam, paid_exam, "Cleared" if paid_exam >= total_exam else "Not Cleared"])
            if total_lab != 0:
                df.append(["Lab Returns HOD Fee", total_lab, paid_lab, "Cleared" if paid_lab >= total_lab else "Not Cleared"])
            
            # Generate certificate
            name, data = getCertificate(student_id, student_name, course, year, df)
            response = HttpResponse(data, content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename=' + name
            return response
            
        except Exception as e:
            return HttpResponse('Error generating certificate: ' + str(e), status=500)

def AdminScreen(request):
    if request.method == 'GET':
        global uname
        if uname:
            context = {'data': 'welcome ' + uname}
        else:
            context = {'data': 'welcome admin'}
        return render(request, 'AdminScreen.html', context)

def EmployeeScreen(request):
    if request.method == 'GET':
        global uname
        if uname:
            context = {'data': 'welcome ' + uname}
        else:
            context = {'data': 'welcome employee'}
        return render(request, 'EmployeeScreen.html', context)

def StudentScreen(request):
    if request.method == 'GET':
        global uname
        student_details = []
        if uname:
            # Fetch all student records for this student_id (multiple course years possible)
            con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
            with con:
                cur = con.cursor()
                cur.execute("select * from student where student_id='"+uname+"' ORDER BY course_year DESC")
                rows = cur.fetchall()
                for row in rows:
                    student_details.append(row)
            
            if student_details:
                # Build student details display
                details_html = '<div class="student-details-container">'
                details_html += '<h3><i class="fa fa-user-graduate"></i> Student Details</h3>'
                details_html += '<div class="student-info-grid">'
                
                for student in student_details:
                    # student record: (student_id, student_name, gender, contact_no, email, course, course_year, password, library_fee, hostel_fee, tution_fee, exam_fee, lab_hod_fee)
                    details_html += '<div class="student-info-card">'
                    details_html += '<h4><i class="fa fa-id-card"></i> Student ID: ' + str(student[0]) + '</h4>'
                    details_html += '<p><strong>Name:</strong> ' + str(student[1] if student[1] else 'N/A') + '</p>'
                    details_html += '<p><strong>Gender:</strong> ' + str(student[2] if student[2] else 'N/A') + '</p>'
                    details_html += '<p><strong>Contact:</strong> ' + str(student[3] if student[3] else 'N/A') + '</p>'
                    details_html += '<p><strong>Email:</strong> ' + str(student[4] if student[4] else 'N/A') + '</p>'
                    details_html += '<p><strong>Course:</strong> ' + str(student[5] if student[5] else 'N/A') + '</p>'
                    details_html += '<p><strong>Course Year:</strong> ' + str(student[6] if student[6] else 'N/A') + '</p>'
                    details_html += '<hr style="margin: 10px 0; border: 1px solid #ddd;">'
                    details_html += '<h5><i class="fa fa-money-bill-wave"></i> Fee Structure:</h5>'
                    details_html += '<p><strong>Library Fee:</strong> ₹' + str(student[8] if student[8] is not None else '0') + '</p>'
                    details_html += '<p><strong>Hostel Fee:</strong> ₹' + str(student[9] if student[9] is not None else '0') + '</p>'
                    details_html += '<p><strong>Tution Fee:</strong> ₹' + str(student[10] if student[10] is not None else '0') + '</p>'
                    details_html += '<p><strong>Exam Fee:</strong> ₹' + str(student[11] if student[11] is not None else '0') + '</p>'
                    details_html += '<p><strong>Lab HOD Fee:</strong> ₹' + str(student[12] if student[12] is not None else '0') + '</p>'
                    details_html += '</div>'
                
                details_html += '</div></div>'
                context = {'data': 'welcome ' + uname, 'student_details': details_html}
            else:
                context = {'data': 'welcome ' + uname, 'student_details': ''}
        else:
            context = {'data': 'welcome student', 'student_details': ''}
        return render(request, 'StudentScreen.html', context)   

def AdminLoginAction(request):
    if request.method == 'POST':
        global uname
        username = request.POST.get('t1', False)
        password = request.POST.get('t2', False)
        if username == 'admin' and password == 'admin':
            context= {'data':'welcome '+username}
            return render(request, 'AdminScreen.html', context)
        else:
            context= {'data':'login failed'}
            return render(request, 'AdminLogin.html', context)
    else:
        return render(request, 'AdminLogin.html', {'data': 'Please use POST method to login'})

def EmployeeLoginAction(request):
    if request.method == 'POST':
        global uname, dept
        username = request.POST.get('t1', False)
        password = request.POST.get('t2', False)
        role = request.POST.get('t3', False)
        index = 0
        con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
        with con:    
            cur = con.cursor()
            cur.execute("select username, password FROM employees where username='"+username+"' and password='"+password+"' and user_role='"+role+"'")
            rows = cur.fetchall()
            for row in rows:
                uname = username
                dept = role
                index = 1
                break		
        if index == 1:
            context= {'data':'welcome '+username}
            return render(request, 'EmployeeScreen.html', context)
        else:
            context= {'data':'login failed'}
            return render(request, 'EmployeeLogin.html', context)
    else:
        return render(request, 'EmployeeLogin.html', {'data': 'Please use POST method to login'})
    
def StudentLoginAction(request):
    if request.method == 'POST':
        global uname
        username = request.POST.get('t1', False)
        password = request.POST.get('t2', False)
        index = 0
        con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
        with con:    
            cur = con.cursor()
            cur.execute("select student_id, password FROM student")
            rows = cur.fetchall()
            for row in rows:
                if row[0] == username and password == row[1]:
                    uname = username
                    index = 1
                    break		
        if index == 1:
            # Fetch and display student details immediately after login
            student_details = []
            if uname:
                # Fetch all student records for this student_id (multiple course years possible)
                con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
                with con:
                    cur = con.cursor()
                    cur.execute("select * from student where student_id='"+uname+"' ORDER BY course_year DESC")
                    rows = cur.fetchall()
                    for row in rows:
                        student_details.append(row)
                
                if student_details:
                    # Build student details display
                    details_html = '<div class="student-details-container">'
                    details_html += '<h3><i class="fa fa-user-graduate"></i> Student Details</h3>'
                    details_html += '<div class="student-info-grid">'
                    
                    for student in student_details:
                        # student record: (student_id, student_name, gender, contact_no, email, course, course_year, password, library_fee, hostel_fee, tution_fee, exam_fee, lab_hod_fee)
                        details_html += '<div class="student-info-card">'
                        details_html += '<h4><i class="fa fa-id-card"></i> Student ID: ' + str(student[0]) + '</h4>'
                        details_html += '<p><strong>Name:</strong> ' + str(student[1] if student[1] else 'N/A') + '</p>'
                        details_html += '<p><strong>Gender:</strong> ' + str(student[2] if student[2] else 'N/A') + '</p>'
                        details_html += '<p><strong>Contact:</strong> ' + str(student[3] if student[3] else 'N/A') + '</p>'
                        details_html += '<p><strong>Email:</strong> ' + str(student[4] if student[4] else 'N/A') + '</p>'
                        details_html += '<p><strong>Course:</strong> ' + str(student[5] if student[5] else 'N/A') + '</p>'
                        details_html += '<p><strong>Course Year:</strong> ' + str(student[6] if student[6] else 'N/A') + '</p>'
                        details_html += '<hr style="margin: 10px 0; border: 1px solid #ddd;">'
                        details_html += '<h5><i class="fa fa-money-bill-wave"></i> Fee Structure:</h5>'
                        details_html += '<p><strong>Library Fee:</strong> ₹' + str(student[8] if student[8] is not None else '0') + '</p>'
                        details_html += '<p><strong>Hostel Fee:</strong> ₹' + str(student[9] if student[9] is not None else '0') + '</p>'
                        details_html += '<p><strong>Tution Fee:</strong> ₹' + str(student[10] if student[10] is not None else '0') + '</p>'
                        details_html += '<p><strong>Exam Fee:</strong> ₹' + str(student[11] if student[11] is not None else '0') + '</p>'
                        details_html += '<p><strong>Lab HOD Fee:</strong> ₹' + str(student[12] if student[12] is not None else '0') + '</p>'
                        details_html += '</div>'
                    
                    details_html += '</div></div>'
                    context = {'data': 'welcome ' + username, 'student_details': details_html}
                else:
                    context = {'data': 'welcome ' + username, 'student_details': ''}
            else:
                context = {'data': 'welcome ' + username, 'student_details': ''}
            return render(request, 'StudentScreen.html', context)
        else:
            context= {'data':'login failed'}
            return render(request, 'StudentLogin.html', context)
    else:
        return render(request, 'StudentLogin.html', {'data': 'Please use POST method to login'})

def ViewPaymentAction(request):
    if request.method == 'POST':
        global uname, dept
        student = request.POST.get('t1', False)
        payments = []
        student_list = []
        
        # Get student list for dropdown
        con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
        with con:
            cur = con.cursor()
            cur.execute("select student_id from student")
            rows = cur.fetchall()
            for row in rows:
                student_list.append(row[0])
        
        # Get payments for selected student with due amounts
        if student:
            con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
            with con:
                cur = con.cursor()
                # Filter by department if logged in as department employee
                if dept:
                    # Only show payments for the logged-in department
                    cur.execute("select * from payments where student_id='"+student+"' and paying_dept='"+dept+"' ORDER BY payment_date ASC, student_id ASC")
                else:
                    # Admin can see all payments
                    cur.execute("select * from payments where student_id='"+student+"' ORDER BY payment_date ASC, student_id ASC")
                rows = cur.fetchall()
                for row in rows:
                    # row structure: (student_id, course_year, paying_dept, amount, payment_date)
                    student_id = row[0]
                    course_year = row[1]
                    department = row[2]
                    payment_amount = float(row[3]) if row[3] else 0
                    payment_date = row[4]
                    
                    # Get total fee for this department
                    total_fee = getDepartmentTotalFee(student_id, course_year, department)
                    
                    # Get cumulative paid amount up to this payment date
                    cumulative_paid = getCumulativePaidAmount(student_id, course_year, department, payment_date)
                    
                    # Calculate remaining due after this payment
                    total_fee_float = float(total_fee) if total_fee else 0.0
                    cumulative_paid_float = float(cumulative_paid) if cumulative_paid else 0.0
                    remaining_due = max(0.0, total_fee_float - cumulative_paid_float)
                    
                    # Round to 2 decimal places to avoid floating point precision issues
                    remaining_due = round(remaining_due, 2)
                    
                    
                    is_cleared = remaining_due <= 0.01
                    
                    enhanced_payment = row + (remaining_due, is_cleared)
                    payments.append(enhanced_payment)
        
        # Determine dashboard based on user type (employee has dept set)
        dashboard_link = '/EmployeeScreen.html' if dept else '/AdminScreen.html'
        context = {
            'students': student_list,
            'payments': payments,
            'selected_student': student,
            'dashboard_link': dashboard_link
        }
        return render(request, 'ViewPayments.html', context)
    else:
        # Get student list for dropdown
        students = []
        con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
        with con:
            cur = con.cursor()
            cur.execute("select student_id from student")
            rows = cur.fetchall()
            for row in rows:
                students.append(row[0])
        # Determine dashboard based on user type (employee has dept set)
        dashboard_link = '/EmployeeScreen.html' if dept else '/AdminScreen.html'
        context = {'students': students, 'payments': [], 'selected_student': '', 'dashboard_link': dashboard_link}
        return render(request, 'ViewPayments.html', context)

def ViewPayments(request):
    if request.method == 'GET':
        global dept
        students = []
        con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
        with con:
            cur = con.cursor()
            cur.execute("select student_id from student")
            rows = cur.fetchall()
            for row in rows:
                students.append(row[0])
        # Determine dashboard based on user type (employee has dept set)
        dashboard_link = '/EmployeeScreen.html' if dept else '/AdminScreen.html'
        context = {'students': students, 'payments': [], 'selected_student': '', 'dashboard_link': dashboard_link}
        return render(request, 'ViewPayments.html', context)

def ViewEmployees(request):
    if request.method == 'GET':
        employees = []
        con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
        with con:
            cur = con.cursor()
            cur.execute("select * from employees")
            rows = cur.fetchall()
            for row in rows:
                employees.append(row)
        context= {'employees': employees}
        return render(request, 'ViewEmployees.html', context)

def UpdateEmployeeForm(request):
    if request.method == 'GET':
        username = request.GET.get('username', False)
        if username:
            employee_data = None
            con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
            with con:
                cur = con.cursor()
                cur.execute("select * from employees where username='"+username+"'")
                row = cur.fetchone()
                if row:
                    employee_data = row
            if employee_data:
                context = {
                    'employee': employee_data,
                    'data': ''
                }
                return render(request, 'UpdateEmployee.html', context)
            else:
                return render(request, 'ViewEmployees.html', {'employees': [], 'data': '<font size=3 color=red>Employee not found.</font>'})
        else:
            return render(request, 'ViewEmployees.html', {'employees': [], 'data': '<font size=3 color=red>Invalid request. Please select an employee to update.</font>'})
    else:
        return render(request, 'ViewEmployees.html', {'employees': [], 'data': '<font size=3 color=red>Invalid request method.</font>'})

def UpdateEmployeeAction(request):
    if request.method == 'POST':
        old_username = request.POST.get('old_username', False)
        employee_name = request.POST.get('t1', False)
        gender = request.POST.get('t2', False)
        contact = request.POST.get('t3', False)
        email = request.POST.get('t4', False)
        qualification = request.POST.get('t5', False)
        experience = request.POST.get('t6', False)
        dept_role = request.POST.get('t7', False)
        username = request.POST.get('t8', False)
        password = request.POST.get('t9', False)
        
        status = "<font size=3 color=red>Database error occurred</font>"
        db_connection = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
        db_cursor = db_connection.cursor()
        
        # Based on INSERT order: emp_name, gender, contact, email, qualification, experience, role, username, password
        # Using column positions or checking actual column names
        query = "UPDATE employees SET emp_name='"+employee_name+"', gender='"+gender+"', contact_no='"+contact+"', email='"+email+"', qualification='"+qualification+"', experience='"+experience+"', user_role='"+dept_role+"', username='"+username+"', password='"+password+"' WHERE username='"+old_username+"'"
        db_cursor.execute(query)
        db_connection.commit()
        
        if db_cursor.rowcount == 1:
            status = "<font size=3 color=blue>Employee details updated successfully</font>"
        else:
            status = "<font size=3 color=red>Failed to update employee. Employee may not exist.</font>"
        
        # Return to ViewEmployees page
        employees = []
        con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
        with con:
            cur = con.cursor()
            cur.execute("select * from employees")
            rows = cur.fetchall()
            for row in rows:
                employees.append(row)
        context = {'employees': employees, 'data': status}
        return render(request, 'ViewEmployees.html', context)
    else:
        return render(request, 'ViewEmployees.html', {'employees': [], 'data': '<font size=3 color=red>Invalid request method. Please use the form to update employee.</font>'})

def DeleteEmployeeAction(request):
    if request.method == 'POST':
        username = request.POST.get('username', False)
        if username:
            status = "<font size=3 color=red>Database error occurred</font>"
            db_connection = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
            db_cursor = db_connection.cursor()
            
            query = "DELETE FROM employees WHERE username='"+username+"'"
            db_cursor.execute(query)
            db_connection.commit()
            
            if db_cursor.rowcount == 1:
                status = "<font size=3 color=blue>Employee deleted successfully</font>"
            else:
                status = "<font size=3 color=red>Failed to delete employee. Employee may not exist.</font>"
        else:
            status = "<font size=3 color=red>Invalid request. Username not provided.</font>"
        
        # Return to ViewEmployees page
        employees = []
        con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
        with con:
            cur = con.cursor()
            cur.execute("select * from employees")
            rows = cur.fetchall()
            for row in rows:
                employees.append(row)
        context = {'employees': employees, 'data': status}
        return render(request, 'ViewEmployees.html', context)
    else:
        return render(request, 'ViewEmployees.html', {'employees': [], 'data': '<font size=3 color=red>Invalid request method.</font>'})    

def AddEmployeeAction(request):
    if request.method == 'POST':
        emp_name = request.POST.get('t1', False)
        gender = request.POST.get('t2', False)
        contact = request.POST.get('t3', False)
        email = request.POST.get('t4', False)
        qualification = request.POST.get('t5', False)
        experience = request.POST.get('t6', False)
        role = request.POST.get('t7', False)
        username = request.POST.get('t8', False)
        password = request.POST.get('t9', False)
        status = "none"
        con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
        with con:    
            cur = con.cursor()
            cur.execute("select username FROM employees")
            rows = cur.fetchall()
            for row in rows:
                if row[0] == username:
                    status = "Username already exists"
                    break
        if status == "none":
            db_connection = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
            db_cursor = db_connection.cursor()
            student_sql_query = "INSERT INTO employees VALUES('"+emp_name+"','"+gender+"','"+contact+"','"+email+"','"+qualification+"','"+experience+"','"+role+"','"+username+"','"+password+"')"
            db_cursor.execute(student_sql_query)
            db_connection.commit()
            print(db_cursor.rowcount, "Record Inserted")
            if db_cursor.rowcount == 1:
                status = "<font size=3 color=blue>Employee details added with User Role as "+role+"</font>"
        context= {'data': status}
        return render(request, 'AddEmployee.html', context)
    else:
        return render(request, 'AddEmployee.html', {'data': '<font size=3 color=red>Invalid request method. Please use the form to add an employee.</font>'})

def AddStudentAction(request):
    if request.method == 'POST':
        student_id = request.POST.get('t0', False)
        student = request.POST.get('t1', False)
        gender = request.POST.get('t2', False)
        contact = request.POST.get('t3', False)
        email = request.POST.get('t4', False)
        course = request.POST.get('t5', False)
        year = request.POST.get('t6', False)
        tution = request.POST.get('t7', False)
        password = request.POST.get('t8', False)
        library = request.POST.get('t9', False)
        hostel = request.POST.get('t10', False)
        exam = request.POST.get('t11', False)
        hod = request.POST.get('t12', False)
        status = "<font size=3 color=red>Database error occured</font>"
        db_connection = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
        db_cursor = db_connection.cursor()
        student_sql_query = "INSERT INTO student VALUES('"+student_id+"','"+student+"','"+gender+"','"+contact+"','"+email+"','"+course+"','"+year+"','"+password+"','"+library+"','"+hostel+"','"+tution+"','"+exam+"','"+hod+"')"
        db_cursor.execute(student_sql_query)
        db_connection.commit()
        print(db_cursor.rowcount, "Record Inserted")
        if db_cursor.rowcount == 1:
            status = "<font size=3 color=blue>Student details added with Student ID as "+student_id+"</font>"
        context= {'data': status}
        return render(request, 'AddStudent.html', context)
    else:
        return render(request, 'AddStudent.html', {'data': '<font size=3 color=red>Invalid request method. Please use the form to add a student.</font>'})

def UpdateStudentForm(request):
    if request.method == 'GET':
        student_id = request.GET.get('student_id', False)
        course_year = request.GET.get('course_year', False)
        if student_id and course_year:
            student_data = None
            con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
            with con:
                cur = con.cursor()
                cur.execute("select * from student where student_id='"+student_id+"' and course_year='"+course_year+"'")
                row = cur.fetchone()
                if row:
                    student_data = row
            if student_data:
                context = {
                    'student': student_data,
                    'data': ''
                }
                return render(request, 'UpdateStudent.html', context)
            else:
                return render(request, 'ViewStudents.html', {'students': [], 'data': '<font size=3 color=red>Student not found.</font>'})
        else:
            return render(request, 'ViewStudents.html', {'students': [], 'data': '<font size=3 color=red>Invalid request. Please select a student to update.</font>'})
    else:
        return render(request, 'ViewStudents.html', {'students': [], 'data': '<font size=3 color=red>Invalid request method.</font>'})

def UpdateStudentAction(request):
    if request.method == 'POST':
        old_student_id = request.POST.get('old_student_id', False)
        old_course_year = request.POST.get('old_course_year', False)
        student_id = request.POST.get('t0', False)
        student_name = request.POST.get('t1', False)
        gender = request.POST.get('t2', False)
        contact = request.POST.get('t3', False)
        email = request.POST.get('t4', False)
        course = request.POST.get('t5', False)
        year = request.POST.get('t6', False)
        tution = request.POST.get('t7', False)
        password = request.POST.get('t8', False)
        library = request.POST.get('t9', False)
        hostel = request.POST.get('t10', False)
        exam = request.POST.get('t11', False)
        hod = request.POST.get('t12', False)
        
        status = "<font size=3 color=red>Database error occurred</font>"
        db_connection = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
        db_cursor = db_connection.cursor()
        
        query = "UPDATE student SET student_id='"+student_id+"', student_name='"+student_name+"', gender='"+gender+"', contact_no='"+contact+"', email='"+email+"', course='"+course+"', course_year='"+year+"', password='"+password+"', library_fee='"+library+"', hostel_fee='"+hostel+"', tution_fee='"+tution+"', exam_fee='"+exam+"', lab_hod_fee='"+hod+"' WHERE student_id='"+old_student_id+"' AND course_year='"+old_course_year+"'"
        db_cursor.execute(query)
        db_connection.commit()
        
        if db_cursor.rowcount == 1:
            status = "<font size=3 color=blue>Student details updated successfully</font>"
        else:
            status = "<font size=3 color=red>Failed to update student. Student may not exist.</font>"
        
        # Return to ViewStudents page
        students = []
        con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
        with con:
            cur = con.cursor()
            cur.execute("select * from student")
            rows = cur.fetchall()
            for row in rows:
                students.append(row)
        context = {'students': students, 'data': status}
        return render(request, 'ViewStudents.html', context)
    else:
        return render(request, 'ViewStudents.html', {'students': [], 'data': '<font size=3 color=red>Invalid request method. Please use the form to update student.</font>'})

def DeleteStudentAction(request):
    if request.method == 'POST':
        student_id = request.POST.get('student_id', False)
        course_year = request.POST.get('course_year', False)
        if student_id and course_year:
            status = "<font size=3 color=red>Database error occurred</font>"
            db_connection = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
            db_cursor = db_connection.cursor()
            
            query = "DELETE FROM student WHERE student_id='"+student_id+"' AND course_year='"+course_year+"'"
            db_cursor.execute(query)
            db_connection.commit()
            
            if db_cursor.rowcount == 1:
                status = "<font size=3 color=blue>Student deleted successfully</font>"
            else:
                status = "<font size=3 color=red>Failed to delete student. Student may not exist.</font>"
        else:
            status = "<font size=3 color=red>Invalid request. Student ID and Course Year not provided.</font>"
        
        # Return to ViewStudents page
        students = []
        con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue',charset='utf8')
        with con:
            cur = con.cursor()
            cur.execute("select * from student")
            rows = cur.fetchall()
            for row in rows:
                students.append(row)
        context = {'students': students, 'data': status}
        return render(request, 'ViewStudents.html', context)
    else:
        return render(request, 'ViewStudents.html', {'students': [], 'data': '<font size=3 color=red>Invalid request method.</font>'})
    
