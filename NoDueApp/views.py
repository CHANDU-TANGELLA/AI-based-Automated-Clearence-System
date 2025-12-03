
# Add these to your existing imports
from transformers import pipeline
import PyPDF2
from django.shortcuts import redirect
from .models import Student, Payment, DocumentSubmission, Employee


from transformers import pipeline
import PyPDF2
from django.shortcuts import redirect
from .models import Student, Payment, DocumentSubmission, Employee


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
from django.db.models import Sum



global uname, dept, df, cleared, student_year, student_name_global, student_course_global

# Initialize global variables
uname = ""
dept = ""
df = []
cleared = "no"
student_year = ""
student_name_global = ""
student_course_global = ""

# Lazy loading for heavy models
_classifier = None

def get_classifier():
    global _classifier
    if _classifier is None:
        print("Loading Zero-Shot Classifier...")
        _classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    return _classifier

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
    con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue_new',charset='utf8')
    with con:
        cur = con.cursor()
        cur.execute("select email from student where student_id='"+student+"'")
        rows = cur.fetchall()
        for row in rows:
            email = row[0]
            break
    sendEmail(email, "Your no due certificate generated and can be downloaded by login to appplication")    

def getTotalFee(student, year):
    try:
        student_obj = Student.objects.get(student_id=student, course_year=year)
        return (
            student_obj.library_fee,
            student_obj.hostel_fee,
            student_obj.tution_fee,
            student_obj.exam_fee,
            student_obj.lab_hod_fee
        )
    except Student.DoesNotExist:
        return 0, 0, 0, 0, 0


def getPaidFee(student, year):
    def get_sum(dept):
        result = Payment.objects.filter(student_id=student, course_year=year, paying_dept=dept).aggregate(Sum('amount'))
        return result['amount__sum'] or 0.0

    tution = get_sum('Accounts')
    library = get_sum('Library')
    hostel = get_sum('Hostel')
    exam = get_sum('Exam Fee Dept')
    lab = get_sum('HOD Lab Returns')
    
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
    try:
        result = Payment.objects.filter(
            student_id=student, 
            course_year=year, 
            paying_dept=department, 
            payment_date__lte=payment_date
        ).aggregate(Sum('amount'))
        return float(result['amount__sum'] or 0.0)
    except Exception as e:
        print(f"Error calculating cumulative paid amount: {e}")
        return 0.0

def getStudentDetails(student_id, year):
    """Get student name and course details from database"""
    student_name = ""
    course = ""
    con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue_new',charset='utf8')
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
        students = Student.objects.all()
        # Determine dashboard based on user type (employee has dept set)
        dashboard_link = '/EmployeeScreen.html' if dept else '/AdminScreen.html'
        context = {'students': students, 'data': '', 'dashboard_link': dashboard_link}
        return render(request, 'ViewStudents.html', context) 


def AcceptFee(request):
    if request.method == 'GET':
        global dept
        students = Student.objects.values_list('student_id', flat=True).distinct()
        
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
        except ValueError:
            status = "<div class='alert-message error'><i class='fa fa-exclamation-circle'></i> Invalid fee amount. Please enter a valid number.</div>"
            context = {'data': status}
            return render(request, 'EmployeeScreen.html', context)
        
        try:
            updated_count = 0
            if dept == "Accounts":
                updated_count = Student.objects.filter(student_id=student, course_year=year).update(tution_fee=fee_value)
            elif dept == "Library":
                updated_count = Student.objects.filter(student_id=student, course_year=year).update(library_fee=fee_value)
            elif dept == "Hostel":
                updated_count = Student.objects.filter(student_id=student, course_year=year).update(hostel_fee=fee_value)
            elif dept == "Exam Fee Dept":
                updated_count = Student.objects.filter(student_id=student, course_year=year).update(exam_fee=fee_value)
            elif dept == "HOD Lab Returns":
                updated_count = Student.objects.filter(student_id=student, course_year=year).update(lab_hod_fee=fee_value)
            else:
                status = "<div class='alert-message error'><i class='fa fa-exclamation-circle'></i> Invalid department. Cannot determine fee type to update.</div>"
                context = {'data': status}
                return render(request, 'EmployeeScreen.html', context)
            
            if updated_count > 0:
                status = "<div class='alert-message success'><i class='fa fa-check-circle'></i> Selected student fee successfully updated</div>"
            else:
                status = "<div class='alert-message error'><i class='fa fa-exclamation-circle'></i> No student found with Student ID: " + str(student) + " and Course Year: " + str(year) + ". Please verify the details.</div>"
                
        except Exception as e:
            status = "<div class='alert-message error'><i class='fa fa-exclamation-circle'></i> An unexpected error occurred: " + str(e) + "</div>"
        
        context = {'data': status}
        return render(request, 'EmployeeScreen.html', context)
    else:
        students = []
        students = Student.objects.values_list('student_id', flat=True).distinct()
        return render(request, 'UpdateFee.html', {'students': students, 'dept': dept if 'dept' in globals() else '', 'fee_type': '', 'fee_label': '', 'data': '<font size=3 color=red>Invalid request method. Please use the form to update fee.</font>'})

def UpdateFee(request):
    if request.method == 'GET':
        global dept
        students = Student.objects.values_list('student_id', flat=True).distinct()
        
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
            con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue_new',charset='utf8')
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
            con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue_new',charset='utf8')
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
        
        try:
            employee = Employee.objects.get(username=username, password=password, user_role=role)
            uname = username
            dept = role
            context= {'data':'welcome '+username}
            return render(request, 'EmployeeScreen.html', context)
        except Employee.DoesNotExist:
            context= {'data':'login failed'}
            return render(request, 'EmployeeLogin.html', context)
    else:
        return render(request, 'EmployeeLogin.html', {'data': 'Please use POST method to login'})
    
def StudentLoginAction(request):
    if request.method == 'POST':
        global uname
        username = request.POST.get('t1', False)
        password = request.POST.get('t2', False)
        
        # Check if student exists
        if Student.objects.filter(student_id=username, password=password).exists():
            uname = username
            
            # Fetch all records for this student
            student_details = Student.objects.filter(student_id=uname).order_by('-course_year')
            
            if student_details:
                # Build student details display
                details_html = '<div class="student-details-container">'
                details_html += '<h3><i class="fa fa-user-graduate"></i> Student Details</h3>'
                details_html += '<div class="student-info-grid">'
                
                for student in student_details:
                    # Map fields
                    details_html += '<div class="student-info-card">'
                    details_html += '<h4><i class="fa fa-id-card"></i> Student ID: ' + str(student.student_id) + '</h4>'
                    details_html += '<p><strong>Name:</strong> ' + str(student.student_name if student.student_name else 'N/A') + '</p>'
                    details_html += '<p><strong>Gender:</strong> ' + str(student.gender if student.gender else 'N/A') + '</p>'
                    details_html += '<p><strong>Contact:</strong> ' + str(student.contact if student.contact else 'N/A') + '</p>'
                    details_html += '<p><strong>Email:</strong> ' + str(student.email if student.email else 'N/A') + '</p>'
                    details_html += '<p><strong>Course:</strong> ' + str(student.course if student.course else 'N/A') + '</p>'
                    details_html += '<p><strong>Course Year:</strong> ' + str(student.course_year if student.course_year else 'N/A') + '</p>'
                    details_html += '<hr style="margin: 10px 0; border: 1px solid #ddd;">'
                    details_html += '<h5><i class="fa fa-money-bill-wave"></i> Fee Structure:</h5>'
                    details_html += '<p><strong>Library Fee:</strong> ₹' + str(student.library_fee) + '</p>'
                    details_html += '<p><strong>Hostel Fee:</strong> ₹' + str(student.hostel_fee) + '</p>'
                    details_html += '<p><strong>Tution Fee:</strong> ₹' + str(student.tution_fee) + '</p>'
                    details_html += '<p><strong>Exam Fee:</strong> ₹' + str(student.exam_fee) + '</p>'
                    details_html += '<p><strong>Lab HOD Fee:</strong> ₹' + str(student.lab_hod_fee) + '</p>'
                    details_html += '</div>'
                
                details_html += '</div></div>'
                context = {'data': 'welcome ' + username, 'student_details': details_html}
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
        
        # 1. Fetch Student List (Using NEW DB)
        con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue_new',charset='utf8')
        with con:
            cur = con.cursor()
            cur.execute("select student_id from student")
            rows = cur.fetchall()
            for row in rows:
                student_list.append(row[0])
        
        # 2. Fetch Payments (Using NEW DB)
        if student:
            con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue_new',charset='utf8')
            with con:
                cur = con.cursor()
                if dept: # If logged in as Employee
                    cur.execute("select * from payments where student_id='"+student+"' and paying_dept='"+dept+"' ORDER BY payment_date DESC")
                else: # If logged in as Admin
                    cur.execute("select * from payments where student_id='"+student+"' ORDER BY payment_date DESC")
                
                rows = cur.fetchall()
                for row in rows:
                    # row: (student_id, year, dept, amount, date)
                    s_id, year, paying_dept, amount, p_date = row
                    
                    # Calculate Remaining Due dynamically
                    total_fee = getDepartmentTotalFee(s_id, year, paying_dept)
                    cumulative_paid = getCumulativePaidAmount(s_id, year, paying_dept, p_date)
                    
                    remaining = max(0.0, float(total_fee) - float(cumulative_paid))
                    is_cleared = remaining <= 0
                    
                    # Append calculated data to row
                    payments.append(row + (round(remaining, 2), is_cleared))
        
        dashboard_link = '/EmployeeScreen.html' if dept else '/AdminScreen.html'
        context = {
            'students': student_list,
            'payments': payments,
            'selected_student': student,
            'dashboard_link': dashboard_link
        }
        return render(request, 'ViewPayments.html', context)
    else:
        # Fallback for GET request
        return ViewPayments(request)

def ViewPayments(request):
    if request.method == 'GET':
        global dept
        students = []
        # Connect to NEW DB
        con = pymysql.connect(host='127.0.0.1',port = 3306,user = 'root', password = 'root', database = 'nodue_new',charset='utf8')
        with con:
            cur = con.cursor()
            cur.execute("select student_id from student")
            rows = cur.fetchall()
            for row in rows:
                students.append(row[0])
                
        dashboard_link = '/EmployeeScreen.html' if dept else '/AdminScreen.html'
        context = {'students': students, 'payments': [], 'selected_student': '', 'dashboard_link': dashboard_link}
        return render(request, 'ViewPayments.html', context)



def ViewEmployees(request):
    if request.method == 'GET':
        employees = []
        try:
            con = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='root', database='nodue_new', charset='utf8')
            with con:
                cur = con.cursor()
                cur.execute("select * from employees")
                employees = cur.fetchall()
        except Exception as e:
            print("Error:", e)
            
        context = {'employees': employees}
        return render(request, 'ViewEmployees.html', context)

def UpdateEmployeeForm(request):
    if request.method == 'GET':
        username = request.GET.get('username', False)
        if username:
            employee_data = None
            
            try:
                # 1. Connect to the NEW database explicitly
                con = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='root', database='nodue_new', charset='utf8')
                with con:
                    cur = con.cursor()
                    # 2. Execute SQL query
                    cur.execute("select * from employees where username='" + username + "'")
                    # 3. Fetch data as a tuple
                    employee_data = cur.fetchone() 
            except Exception as e:
                print("Error fetching employee:", e)

            if employee_data:
                # ERROR WAS HERE: Ensure 'context = {' includes the opening brace
                context = {
                    'employee': employee_data,
                    'data': ''
                }
                return render(request, 'UpdateEmployee.html', context)
            else:
                return render(request, 'ViewEmployees.html', {'employees': [], 'data': '<font size=3 color=red>Employee not found in nodue_new database.</font>'})
        else:
            return render(request, 'ViewEmployees.html', {'employees': [], 'data': '<font size=3 color=red>Invalid request. Please select an employee to update.</font>'})
    else:
        return render(request, 'ViewEmployees.html', {'employees': [], 'data': '<font size=3 color=red>Invalid request method.</font>'})
def UpdateEmployeeAction(request):
    if request.method == 'POST':
        old_username = request.POST.get('old_username', False)
        emp_name = request.POST.get('t1', False)
        gender = request.POST.get('t2', False)
        contact = request.POST.get('t3', False)
        email = request.POST.get('t4', False)
        qualification = request.POST.get('t5', False)
        experience = request.POST.get('t6', False)
        role = request.POST.get('t7', False)
        username = request.POST.get('t8', False)
        password = request.POST.get('t9', False)
        
        status = "<font size=3 color=red>Database error occurred</font>"
        
        try:
            # Connect to 'nodue_new'
            db_connection = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='root', database='nodue_new', charset='utf8')
            db_cursor = db_connection.cursor()
            
            # Execute Raw SQL Update
            query = """
                UPDATE employees 
                SET emp_name=%s, gender=%s, contact_no=%s, email=%s, 
                    qualification=%s, experience=%s, user_role=%s, 
                    username=%s, password=%s 
                WHERE username=%s
            """
            db_cursor.execute(query, (emp_name, gender, contact, email, qualification, experience, role, username, password, old_username))
            db_connection.commit()
            
            if db_cursor.rowcount >= 0:
                status = "<font size=3 color=blue>Employee details updated successfully</font>"
            else:
                status = "<font size=3 color=red>Failed to update. Employee may not exist.</font>"
                
            db_cursor.close()
            db_connection.close()
            
        except Exception as e:
            status = f"<font size=3 color=red>Error: {str(e)}</font>"
        
        # Fetch updated list for display
        employees = []
        try:
            con = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='root', database='nodue_new', charset='utf8')
            with con:
                cur = con.cursor()
                cur.execute("select * from employees")
                employees = cur.fetchall()
        except Exception as e:
            print("Error fetching list:", e)

        context = {'employees': employees, 'data': status}
        return render(request, 'ViewEmployees.html', context)
    else:
        return render(request, 'ViewEmployees.html', {'employees': [], 'data': '<font size=3 color=red>Invalid request method.</font>'})

def DeleteEmployeeAction(request):
    if request.method == 'POST':
        username = request.POST.get('username', False)
        
        try:
            employee = Employee.objects.filter(username=username).first()
            if employee:
                employee.delete()
                status = "<font size=3 color=blue>Employee deleted successfully</font>"
            else:
                status = "<font size=3 color=red>Failed to delete employee. Employee may not exist.</font>"
        except Exception as e:
            status = f"<font size=3 color=red>Database error occurred: {str(e)}</font>"
            
        # Return to ViewEmployees page
        employees = Employee.objects.all()
        context = {'employees': employees, 'data': status}
        return render(request, 'ViewEmployees.html', context)
    else:
        return render(request, 'ViewEmployees.html', {'employees': [], 'data': '<font size=3 color=red>Invalid request method. Please use the form to delete employee.</font>'})

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
        
        try:
            if Employee.objects.filter(username=username).exists():
                status = "Username already exists"
            else:
                Employee.objects.create(
                    emp_name=emp_name,
                    gender=gender,
                    contact_no=contact,
                    email=email,
                    qualification=qualification,
                    experience=experience,
                    user_role=role,
                    username=username,
                    password=password
                )
                status = "<font size=3 color=blue>Employee details added with User Role as "+role+"</font>"
        except Exception as e:
            print(e)
            status = "<font size=3 color=red>Database error occurred: " + str(e) + "</font>"
            
        context= {'data': status}
        return render(request, 'AddEmployee.html', context)
    else:
        return render(request, 'AddEmployee.html', {'data': '<font size=3 color=red>Invalid request method. Please use the form to add an employee.</font>'})

def AddStudentAction(request):
    if request.method == 'POST':
        # ... (Get all variables t0 to t12 like you have now) ...
        student_id = request.POST.get('t0', False)
        # (keep all the other variable getters)
        
        try:
            con = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='root', database='nodue_new', charset='utf8')
            with con:
                cur = con.cursor()
                
                # Check if exists
                cur.execute("SELECT * FROM student WHERE student_id=%s AND course_year=%s", (student_id, year))
                if cur.fetchone():
                    status = "<font size=3 color=red>Student ID already exists for this year</font>"
                else:
                    # Insert
                    query = """INSERT INTO student 
                    (student_id, student_name, gender, contact_no, email, course, course_year, tution_fee, password, library_fee, hostel_fee, exam_fee, lab_hod_fee) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                    
                    cur.execute(query, (student_id, student_name, gender, contact, email, course, year, tution, password, library, hostel, exam, hod))
                    status = "<font size=3 color=blue>Student details added successfully</font>"
                    
        except Exception as e:
            status = f"<font size=3 color=red>Error: {str(e)}</font>"
            
        context= {'data': status}
        return render(request, 'AddStudent.html', context)
    else:
        return render(request, 'AddStudent.html', {'data': 'Invalid request'})
def UpdateStudentForm(request):
    if request.method == 'GET':
        student_id = request.GET.get('student_id', False)
        course_year = request.GET.get('course_year', False)
        if student_id and course_year:
            student_data = Student.objects.filter(student_id=student_id, course_year=course_year).first()
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
        
        try:
            # Check if student exists
            student_obj = Student.objects.filter(student_id=old_student_id, course_year=old_course_year).first()
            if student_obj:
                # Update fields
                student_obj.student_id = student_id
                student_obj.student_name = student_name
                student_obj.gender = gender
                student_obj.contact = contact
                student_obj.email = email
                student_obj.course = course
                student_obj.course_year = year
                student_obj.password = password
                student_obj.tution_fee = float(tution) if tution else 0.0
                student_obj.library_fee = float(library) if library else 0.0
                student_obj.hostel_fee = float(hostel) if hostel else 0.0
                student_obj.exam_fee = float(exam) if exam else 0.0
                student_obj.lab_hod_fee = float(hod) if hod else 0.0
                student_obj.save()
                
                status = "<font size=3 color=blue>Student details updated successfully</font>"
            else:
                status = "<font size=3 color=red>Failed to update student. Student may not exist.</font>"
        except Exception as e:
            status = f"<font size=3 color=red>Database error occurred: {str(e)}</font>"
        
        # Return to ViewStudents page
        students = Student.objects.all()
        context = {'students': students, 'data': status}
        return render(request, 'ViewStudents.html', context)
    else:
        return render(request, 'ViewStudents.html', {'students': [], 'data': '<font size=3 color=red>Invalid request method. Please use the form to update student.</font>'})

def DeleteStudentAction(request):
    if request.method == 'POST':
        student_id = request.POST.get('student_id', False)
        course_year = request.POST.get('course_year', False)
        
        try:
            student = Student.objects.filter(student_id=student_id, course_year=course_year).first()
            if student:
                student.delete()
                status = "<font size=3 color=blue>Student deleted successfully</font>"
            else:
                status = "<font size=3 color=red>Failed to delete student. Student may not exist.</font>"
        except Exception as e:
            status = f"<font size=3 color=red>Database error occurred: {str(e)}</font>"
            
        # Return to ViewStudents page
        students = Student.objects.all()
        context = {'students': students, 'data': status}
        return render(request, 'ViewStudents.html', context)
    else:
        return render(request, 'ViewStudents.html', {'students': [], 'data': '<font size=3 color=red>Invalid request method. Please use the form to delete student.</font>'})
    





# --- NEW AI & PAYMENT FUNCTIONS START HERE ---



def analyze_document_content(file_path, expected_category):
    """
    Extracts text from a PDF and uses AI to verify if it matches the expected category.
    """
    try:
        # 1. Extract Text from PDF
        text_content = ""
        with open(file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page in pdf_reader.pages:
                text_content += page.extract_text()
        
        # Limit text to first 1000 chars for speed
        text_content = text_content[:1000]

        if not text_content.strip():
            return False, 0.0, "Empty or unreadable document"

        # 2. Define labels we want the AI to look for
        candidate_labels = ["tuition fee receipt", "library no due certificate", "hostel clearance form", "medical certificate", "irrelevant document"]

        # 3. Perform AI Classification
        result = get_classifier()(text_content, candidate_labels)
        
        # Get the highest scoring label
        top_label = result['labels'][0]
        confidence = result['scores'][0]

        # 4. Decision Logic
        if top_label == expected_category and confidence > 0.6:  # 60% confidence threshold
            return True, confidence, f"Verified as {top_label}"
        else:
            return False, confidence, f"Document appears to be {top_label}, but expected {expected_category}"

    except Exception as e:
        return False, 0.0, str(e)

def UploadDocument(request):
    if request.method == 'POST':
        global uname
        student_id = request.POST.get('student_id')
        dept = request.POST.get('department')
        
        if 'document' not in request.FILES:
             return render(request, 'StudentScreen.html', {'data': "<div class='alert-message error'>No file uploaded.</div>"})
             
        uploaded_file = request.FILES['document']
        
        # 1. Save the file
        fs = FileSystemStorage()
        filename = fs.save(uploaded_file.name, uploaded_file)
        file_path = fs.path(filename)

        # 2. Determine what kind of document we expect
        expected_category = "irrelevant document"
        if dept == "Library":
            expected_category = "library no due certificate"
        elif dept == "Accounts":
            expected_category = "tuition fee receipt"
        elif dept == "Hostel":
            expected_category = "hostel clearance form"

        # 3. Call the AI Verification Function
        is_valid, confidence, message = analyze_document_content(file_path, expected_category)

        # 4. Update Database
        status_text = "Cleared" if is_valid else "Rejected"
        
        # 4. Update Database
        status_text = "Cleared" if is_valid else "Rejected"
        
        try:
            # Create DocumentSubmission record
            DocumentSubmission.objects.create(
                student_id=student_id,
                department=dept,
                file_path=filename, # storing filename relative to media root
                ai_verification_status=status_text,
                ai_confidence_score=confidence
            )
            
            # IF AI verifies it, automatically update the main student fee table
            if is_valid:
                # Find the student with the latest course year
                student = Student.objects.filter(student_id=student_id).order_by('-course_year').first()
                
                if student:
                    if dept == "Library":
                        student.library_fee = 0
                    elif dept == "Accounts":
                        student.tution_fee = 0
                    elif dept == "Hostel":
                        student.hostel_fee = 0
                    # Add other departments as needed
                    student.save()
                    
        except Exception as e:
            print(f"Error updating database: {e}")
            return render(request, 'StudentScreen.html', {'data': f"<div class='alert-message error'>Database error: {str(e)}</div>"})


        # 5. Return response to UI
        if is_valid:
            msg = f"<div class='alert-message success'>AI Verification Successful! ({confidence*100:.1f}% confidence). Your {dept} due is cleared.</div>"
        else:
            msg = f"<div class='alert-message error'>AI Verification Failed. Reason: {message}</div>"
            
        return render(request, 'StudentScreen.html', {'data': msg})

    # GET request - show form
    global uname
    return render(request, 'UploadDocument.html', {'student_id': uname})


def StudentPayDues(request):
    """
    Displays a form for the student to select a department and pay the pending due.
    """
    if request.method == 'GET':
        global uname 
        if not uname:
            return render(request, 'StudentLogin.html', {'data': 'Please login first'})
            
        student_id = uname
        year = ""
        con = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='root', database='nodue_new', charset='utf8')
        with con:
            cur = con.cursor()
            cur.execute("select course_year from student where student_id=%s ORDER BY course_year DESC LIMIT 1", (student_id,))
            row = cur.fetchone()
            if row:
                year = row[0]
        
        if not year:
            return render(request, 'StudentScreen.html', {'data': 'No academic record found.'})

        # Calculate dues for all departments
        total_library, total_hostel, total_tution, total_exam, total_lab = getTotalFee(student_id, year)
        paid_library, paid_hostel, paid_tution, paid_exam, paid_lab = getPaidFee(student_id, year)

        # Helper to calculate pending
        def calc_due(total, paid):
            t = float(total) if total else 0.0
            p = float(paid) if paid else 0.0
            return max(0.0, t - p)

        dues = {
            'Accounts': {'total': total_tution, 'paid': paid_tution, 'pending': calc_due(total_tution, paid_tution)},
            'Library': {'total': total_library, 'paid': paid_library, 'pending': calc_due(total_library, paid_library)},
            'Hostel': {'total': total_hostel, 'paid': paid_hostel, 'pending': calc_due(total_hostel, paid_hostel)},
            'Exam Fee Dept': {'total': total_exam, 'paid': paid_exam, 'pending': calc_due(total_exam, paid_exam)},
            'HOD Lab Returns': {'total': total_lab, 'paid': paid_lab, 'pending': calc_due(total_lab, paid_lab)},
        }

        # Filter only departments with pending dues
        pending_dues = {k: v for k, v in dues.items() if v['pending'] > 0}

        context = {
            'student_id': student_id,
            'year': year,
            'dues': pending_dues,
            'has_dues': bool(pending_dues)
        }
        return render(request, 'StudentPayDues.html', context)

def StudentPayDuesAction(request):
    """
    Processes the payment submission from the student.
    """
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        year = request.POST.get('year')
        dept = request.POST.get('department')
        amount = request.POST.get('amount')
        
        if not amount or float(amount) <= 0:
             return render(request, 'StudentScreen.html', {'data': "<div class='alert-message error'>Invalid amount.</div>"})

        try:
            amount_val = float(amount)
            dd = str(date.today())
            
            con = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='root', database='nodue_new', charset='utf8')
            with con:
                cur = con.cursor()
                insert_query = "INSERT INTO payments (student_id, course_year, paying_dept, amount, payment_date) VALUES (%s, %s, %s, %s, %s)"
                cur.execute(insert_query, (student_id, year, dept, amount_val, dd))
                con.commit()
                
            msg = f"<div class='alert-message success'>Payment of {amount} for {dept} successful! Database updated.</div>"
            return render(request, 'StudentScreen.html', {'data': msg})
            
        except Exception as e:
            return render(request, 'StudentScreen.html', {'data': f"<div class='alert-message error'>Error processing payment: {str(e)}</div>"})

    return redirect('StudentScreen')










def get_fee_receipt(student_id, department, amount, date_str):
    """
    Generates a PDF Fee Receipt for a single transaction.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                            rightMargin=0.75*inch, leftMargin=0.75*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # --- Title ---
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=24, spaceAfter=20)
    elements.append(Paragraph("OFFICIAL FEE RECEIPT", title_style))
    elements.append(Spacer(1, 0.2*inch))

    # --- Receipt Details Table ---
    # We construct a simple table for the receipt info
    data = [
        ["Receipt No:", hashlib.sha256((student_id + date_str + department).encode()).hexdigest()[:10].upper()],
        ["Date:", date_str],
        ["Student ID:", student_id],
        ["Department:", department],
        ["Payment Mode:", "Credit Card / Online"],
        ["Amount Paid:", f"Rs. {amount}"],
        ["Payment Status:", "SUCCESSFUL"]
    ]

    t = Table(data, colWidths=[2.5*inch, 3*inch])
    t.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 12),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BACKGROUND', (0,0), (0,-1), colors.lightgrey),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.5*inch))

    # --- Footer / Verification Note ---
    # This text is crucial for the AI to "read" and verify the document later
    note_style = ParagraphStyle('Note', parent=styles['Normal'], fontSize=10, textColor=colors.grey)
    elements.append(Paragraph(f"This document certifies that {student_id} has cleared the dues for {department}.", styles['Normal']))
    elements.append(Spacer(1, 0.1*inch))
    elements.append(Paragraph("This is a computer-generated receipt valid for AI Document Verification.", note_style))

    doc.build(elements)
    pdf_data = buffer.getvalue()
    buffer.close()
    
    filename = f"Receipt_{student_id}_{department}.pdf"
    return filename, pdf_data






def StudentPayDuesAction(request):
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        year = request.POST.get('year')
        dept = request.POST.get('department')
        amount = request.POST.get('amount')
        
        if not amount or float(amount) <= 0:
             return render(request, 'StudentScreen.html', {'data': "<div class='alert-message error'>Invalid amount.</div>"})

        try:
            amount_val = float(amount)
            dd = str(date.today())
            
            con = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='root', database='nodue_new', charset='utf8')
            with con:
                cur = con.cursor()
                insert_query = "INSERT INTO payments (student_id, course_year, paying_dept, amount, payment_date) VALUES (%s, %s, %s, %s, %s)"
                cur.execute(insert_query, (student_id, year, dept, amount_val, dd))
                con.commit()
            
            # --- GENERATE RECEIPT ---
            filename, pdf_data = get_fee_receipt(student_id, dept, amount, dd)
            
            # Return the PDF as a download
            response = HttpResponse(pdf_data, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
            
        except Exception as e:
            return render(request, 'StudentScreen.html', {'data': f"<div class='alert-message error'>Error processing payment: {str(e)}</div>"})

    return redirect('StudentScreen')




def AcceptFeeAction(request):
    if request.method == 'POST':
        global uname, dept # Assumes dept is the logged-in employee's department
        student = request.POST.get('t1', False)
        fee = request.POST.get('t2', False)
        year = request.POST.get('t3', False)
        
        # ... [Keep your existing validation logic here] ...
        
        try:
            db_connection = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='root', database='nodue_new', charset='utf8')
            with db_connection:
                db_cursor = db_connection.cursor()
                
                # Check student existence logic...
                # (Keep your existing check_query logic here)

                # Insert Payment
                dd = str(date.today())
                insert_query = "INSERT INTO payments (student_id, course_year, paying_dept, amount, payment_date) VALUES (%s, %s, %s, %s, %s)"
                db_cursor.execute(insert_query, (student, year, dept, fee, dd))
                db_connection.commit()
                
                # --- GENERATE RECEIPT ---
                filename, pdf_data = get_fee_receipt(student, dept, fee, dd)
                
                # Return the PDF as a download
                response = HttpResponse(pdf_data, content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response

        except Exception as e:
            status = "<div class='alert-message error'>Error: " + str(e) + "</div>"
            return render(request, 'EmployeeScreen.html', {'data': status})
            
    # Handle GET or other cases...
    return render(request, 'EmployeeScreen.html', {'data': 'Invalid Request'})



# --- AI Configuration ---
# Initialize Zero-Shot Classifier (Downloads model on first run)
classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

def analyze_document_content(file_path, expected_category):
    """
    Helper function: Extracts text from a PDF and uses AI to verify it.
    """
    try:
        # 1. Extract Text from PDF
        text_content = ""
        with open(file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page in pdf_reader.pages:
                text_content += page.extract_text()
        
        # Limit text to first 1000 chars for speed
        text_content = text_content[:1000]

        if not text_content.strip():
            return False, 0.0, "Empty or unreadable document"

        # 2. Define labels the AI looks for
        candidate_labels = ["tuition fee receipt", "library no due certificate", "hostel clearance form", "medical certificate", "irrelevant document"]

        # 3. Perform AI Classification
        result = classifier(text_content, candidate_labels)
        
        # Get the highest scoring label
        top_label = result['labels'][0]
        confidence = result['scores'][0]

        # 4. Decision Logic (Threshold 0.6 means 60% confidence)
        if top_label == expected_category and confidence > 0.6:
            return True, confidence, f"Verified as {top_label}"
        else:
            return False, confidence, f"Document appears to be {top_label}, but expected {expected_category}"

    except Exception as e:
        return False, 0.0, str(e)


def UploadDocument(request):
    """
    View to handle file upload and save to 'nodue_new' database.
    """
    if request.method == 'POST':
        global uname
        student_id = request.POST.get('student_id')
        dept = request.POST.get('department')
        
        # Check if file is selected
        if 'document' not in request.FILES:
             msg = "<div class='alert alert-danger'>No file uploaded.</div>"
             return render(request, 'StudentScreen.html', {'data': msg})
             
        uploaded_file = request.FILES['document']
        
        # 1. Save the file to media directory
        fs = FileSystemStorage()
        filename = fs.save(uploaded_file.name, uploaded_file)
        file_path = fs.path(filename)

        # 2. Determine expected document type
        expected_category = "irrelevant document"
        if dept == "Accounts":
            expected_category = "tuition fee receipt"
        elif dept == "Library":
            expected_category = "library no due certificate"
        elif dept == "Hostel":
            expected_category = "hostel clearance form"

        # 3. Call AI Verification
        is_valid, confidence, message = analyze_document_content(file_path, expected_category)

        # 4. Update Database (nodue_new)
        status_text = "Cleared" if is_valid else "Rejected"
        
        try:
            # Connect to NEW database
            con = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='root', database='nodue_new', charset='utf8')
            with con:
                cur = con.cursor()
                
                # Insert document record
                insert_query = """
                    INSERT INTO document_submissions 
                    (student_id, department, file_path, ai_verification_status, ai_confidence_score)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cur.execute(insert_query, (student_id, dept, file_path, status_text, confidence))
                
                # IF AI verifies it, update the student's main fee record
                if is_valid:
                    # Find the student's latest year
                    cur.execute("select course_year from student where student_id=%s ORDER BY course_year DESC LIMIT 1", (student_id,))
                    yr_row = cur.fetchone()
                    year = yr_row[0] if yr_row else ""
                    
                    if year:
                        if dept == "Library":
                            cur.execute("UPDATE student SET library_fee = 0 WHERE student_id = %s AND course_year = %s", (student_id, year))
                        elif dept == "Accounts":
                            cur.execute("UPDATE student SET tution_fee = 0 WHERE student_id = %s AND course_year = %s", (student_id, year))
                        elif dept == "Hostel":
                            cur.execute("UPDATE student SET hostel_fee = 0 WHERE student_id = %s AND course_year = %s", (student_id, year))
                            
            con.commit()

            # 5. Success/Failure Message
            if is_valid:
                msg = f"<div class='alert alert-success'><strong>AI Verification Successful!</strong><br>Confidence: {confidence*100:.1f}%<br>Status: Your {dept} due is now CLEARED.</div>"
            else:
                msg = f"<div class='alert alert-danger'><strong>AI Verification Failed.</strong><br>Reason: {message}<br>Please upload a valid {expected_category}.</div>"
                
            return render(request, 'StudentScreen.html', {'data': msg})

        except Exception as e:
            msg = f"<div class='alert alert-danger'>Database Error: {str(e)}</div>"
            return render(request, 'StudentScreen.html', {'data': msg})

    # GET Request: Show the upload form
    global uname
    return render(request, 'UploadDocument.html', {'student_id': uname})