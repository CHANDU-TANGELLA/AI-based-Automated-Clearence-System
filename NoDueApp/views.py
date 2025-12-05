from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.core.files.storage import FileSystemStorage
import pymysql
import hashlib
import smtplib
from datetime import date, datetime
import io
import os
import zipfile
import qrcode
from PIL import Image as PILImage

# PDF Generation Imports
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

# AI Imports
from transformers import pipeline
import PyPDF2

# Global Variables
global uname, dept, df, cleared, student_year, student_name_global, student_course_global
uname = ""
dept = ""
df = []
cleared = "no"
student_year = ""
student_name_global = ""
student_course_global = ""

# --- DATABASE HELPER ---
def get_db_connection():
    return pymysql.connect(host='127.0.0.1', port=3306, user='root', password='root', database='nodue_new', charset='utf8')

# Lazy loading for AI model
_classifier = None
def get_classifier():
    global _classifier
    if _classifier is None:
        print("Loading Zero-Shot Classifier...")
        _classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
    return _classifier

# --- Email & Utility Functions ---

def sendEmail(email, msg):
    # Configure your SMTP settings here if needed
    pass 

def getMail(student):
    email = ""
    try:
        con = get_db_connection()
        with con:
            cur = con.cursor()
            cur.execute("select email from student where student_id=%s", (student,))
            row = cur.fetchone()
            if row:
                email = row[0]
        if email:
            sendEmail(email, "Your no due certificate generated and can be downloaded by login to application")
    except Exception as e:
        print(f"Error sending mail: {e}")

def getTotalFee(student, year):
    library = hostel = tution = exam = lab = 0
    try:
        con = get_db_connection()
        with con:
            cur = con.cursor()
            cur.execute("select library_fee, hostel_fee, tution_fee, exam_fee, lab_hod_fee from student where student_id=%s and course_year=%s", (student, year))
            row = cur.fetchone()
            if row:
                library, hostel, tution, exam, lab = row
    except Exception as e:
        print(f"Error getting total fee: {e}")
    
    # Handle None values
    return (float(library or 0), float(hostel or 0), float(tution or 0), float(exam or 0), float(lab or 0))

def getPaidFee(student, year):
    def get_sum(dept):
        con = get_db_connection()
        with con:
            cur = con.cursor()
            cur.execute("select sum(amount) from payments where paying_dept=%s and student_id=%s and course_year=%s", (dept, student, year))
            row = cur.fetchone()
            return float(row[0]) if row and row[0] else 0.0

    tution = get_sum('Accounts')
    library = get_sum('Library')
    hostel = get_sum('Hostel')
    exam = get_sum('Exam Fee Dept')
    lab = get_sum('HOD Lab Returns')
    
    return library, hostel, tution, exam, lab

def getDepartmentTotalFee(student, year, department):
    l, h, t, e, lab = getTotalFee(student, year)
    if department == "Accounts": return t
    if department == "Library": return l
    if department == "Hostel": return h
    if department == "Exam Fee Dept": return e
    if department == "HOD Lab Returns": return lab
    return 0.0

def getCumulativePaidAmount(student, year, department, payment_date):
    amount = 0.0
    try:
        con = get_db_connection()
        with con:
            cur = con.cursor()
            cur.execute("SELECT sum(amount) FROM payments WHERE student_id=%s AND course_year=%s AND paying_dept=%s AND payment_date <= %s", (student, year, department, payment_date))
            row = cur.fetchone()
            if row and row[0]:
                amount = float(row[0])
    except Exception as e:
        print(f"Error calculating cumulative: {e}")
    return amount

def getStudentDetails(student_id, year):
    name = ""
    course = ""
    try:
        con = get_db_connection()
        with con:
            cur = con.cursor()
            cur.execute("select student_name, course from student where student_id=%s and course_year=%s", (student_id, year))
            row = cur.fetchone()
            if row:
                name, course = row
    except:
        pass
    return name, course

# --- PDF Generation Helpers ---

def add_border(canvas, doc):
    """Adds a professional border and footer to every PDF page"""
    canvas.saveState()
    
    # Outer Border
    canvas.setStrokeColor(HexColor('#1a237e'))
    canvas.setLineWidth(4)
    canvas.rect(0.4*inch, 0.4*inch, A4[0]-0.8*inch, A4[1]-0.8*inch)
    
    # Inner Thin Border
    canvas.setStrokeColor(HexColor('#eea412')) # Orange accent
    canvas.setLineWidth(1)
    canvas.rect(0.5*inch, 0.5*inch, A4[0]-1.0*inch, A4[1]-1.0*inch)
    
    # Footer Text
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.grey)
    canvas.drawCentredString(A4[0]/2, 0.75*inch, "This is a computer-generated document. No signature required.")
    canvas.drawCentredString(A4[0]/2, 0.65*inch, "Vishnu Institute of Technology :: AI Clearance System")
    
    canvas.restoreState()

def get_logo_image(width=1.5*inch):
    """Helper to safely get the logo image"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Try different common paths based on your upload structure
    paths = [
        os.path.join(current_dir, 'static', 'css', 'logo_red.png'),
        os.path.join(current_dir, 'static', 'images', 'logo_red.png'),
        os.path.join(current_dir, 'static', 'logo_red.png')
    ]
    
    for p in paths:
        if os.path.exists(p):
            return RLImage(p, width=width, height=0.5*inch, kind='proportional')
    return None

def getCertificate(student_id, student_name, course, year, fee_data):
    """Generates the Official No Due Certificate with QR Code"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.75*inch, leftMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)
    
    elements = []
    styles = getSampleStyleSheet()
    
    # --- 1. Header Section (Logo + QR Code) ---
    # We use a table to put Logo on Left and QR on Right
    
    # Load Logo
    logo = get_logo_image(width=2.5*inch)
    
    # Generate QR Code
    cert_hash = hashlib.sha256((student_id + " No Due Certificate " + year).encode()).hexdigest()[:15]
    qr_data = f"Student: {student_id}\nYear: {year}\nHash: {cert_hash}\nStatus: VERIFIED CLEARED"
    
    qr = qrcode.QRCode(box_size=10, border=1)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    qr_buffer = io.BytesIO()
    img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)
    qr_image = RLImage(qr_buffer, width=1.2*inch, height=1.2*inch)
    
    # Header Table
    header_data = [[logo if logo else "", qr_image]]
    header_table = Table(header_data, colWidths=[4.5*inch, 2*inch])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (0,0), 'LEFT'),   # Logo Left
        ('ALIGN', (1,0), (1,0), 'RIGHT'),  # QR Right
        ('VALIGN', (0,0), (-1,-1), 'TOP')
    ]))
    elements.append(header_table)
    
    elements.append(Spacer(1, 0.2*inch))
    
    # --- 2. College Name ---
    header = Paragraph("VISHNU INSTITUTE OF TECHNOLOGY", 
                      ParagraphStyle('H1', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=20, textColor=HexColor('#1a237e'), fontName='Helvetica-Bold'))
    elements.append(header)
    elements.append(Paragraph("Bhimavaram, Andhra Pradesh", 
                      ParagraphStyle('Sub', parent=styles['Normal'], alignment=TA_CENTER, fontSize=12)))
    elements.append(Spacer(1, 0.4*inch))
    
    # --- 3. Title ---
    title = Paragraph("NO DUE CERTIFICATE", 
                     ParagraphStyle('Title', parent=styles['Heading2'], alignment=TA_CENTER, fontSize=18, textColor=HexColor('#000000'), spaceAfter=20))
    elements.append(title)
    
    # --- 4. Body Text ---
    student_display = student_name if student_name else student_id
    cert_text = f"""
    This is to certify that <b>{student_display}</b> (Student ID: <b>{student_id}</b>), 
    pursuing <b>{course}</b> in the academic year <b>{year}</b>, has successfully cleared all outstanding dues 
    with the institution.
    """
    elements.append(Paragraph(cert_text, ParagraphStyle('Body', parent=styles['Normal'], fontSize=12, leading=18, alignment=TA_JUSTIFY)))
    elements.append(Spacer(1, 0.3*inch))
    
    # --- 5. Fee Table ---
    table_data = [['Department / Fee Type', 'Total Fee', 'Paid Amount', 'Status']]
    for row in fee_data[1:]:
        status_color = colors.green if row[3] == "Cleared" else colors.red
        status_cell = Paragraph(f"<b><font color='{status_color}'>{row[3]}</font></b>", styles['Normal'])
        table_data.append([str(row[0]), f"Rs. {row[1]}", f"Rs. {row[2]}", status_cell])
        
    t = Table(table_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch, 1.2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor('#1a237e')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.whitesmoke, colors.white])
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.5*inch))
    
    # --- 6. Signatures ---
    sig_data = [
        ["", "", ""],
        ["_______________________", "", "_______________________"],
        ["Administrative Officer", "", "Principal"]
    ]
    sig_table = Table(sig_data, colWidths=[2.5*inch, 1.5*inch, 2.5*inch])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,2), (-1,2), 'Helvetica-Bold'),
        ('TOPPADDING', (0,1), (-1,1), 40)
    ]))
    elements.append(sig_table)
    
    # Build
    doc.build(elements, onFirstPage=add_border, onLaterPages=add_border)
    pdf_data = buffer.getvalue()
    buffer.close()
    return f"{student_id}_Certificate.pdf", pdf_data

# --- Views ---

def index(request):
    global uname, dept
    
    # Determine dashboard link based on login state
    dashboard_link = ""
    user_role = ""
    
    if uname:
        if uname == 'admin':
            dashboard_link = "/AdminScreen.html"
            user_role = "Admin"
        elif dept:
            dashboard_link = "/EmployeeScreen.html"
            user_role = f"Employee ({dept})"
        else:
            dashboard_link = "/StudentScreen.html"
            user_role = "Student"
            
    return render(request, 'index.html', {'uname': uname, 'dashboard_link': dashboard_link, 'user_role': user_role})

def Logout(request):
    global uname, dept
    uname = ""
    dept = ""
    return redirect('/')

def AdminLogin(request):
    return render(request, 'AdminLogin.html', {})

def EmployeeLogin(request):
    return render(request, 'EmployeeLogin.html', {})

def StudentLogin(request):
    return render(request, 'StudentLogin.html', {})

def AddEmployee(request):
    return render(request, 'AddEmployee.html', {})

def AddStudent(request):
    return render(request, 'AddStudent.html', {})

def AdminLoginAction(request):
    if request.method == 'POST':
        global uname
        username = request.POST.get('t1')
        password = request.POST.get('t2')
        if username == 'admin' and password == 'admin':
            uname = 'admin'
            return render(request, 'AdminScreen.html', {'data': f'welcome {username}'})
        return render(request, 'AdminLogin.html', {'data': 'login failed'})
    return render(request, 'AdminLogin.html')

def EmployeeLoginAction(request):
    if request.method == 'POST':
        global uname, dept
        username = request.POST.get('t1')
        password = request.POST.get('t2')
        role = request.POST.get('t3')
        
        con = get_db_connection()
        with con:
            cur = con.cursor()
            cur.execute("select * from employees where username=%s and password=%s and user_role=%s", (username, password, role))
            if cur.fetchone():
                uname = username
                dept = role
                return render(request, 'EmployeeScreen.html', {'data': f'welcome {username}'})
        
        return render(request, 'EmployeeLogin.html', {'data': 'login failed'})
    return render(request, 'EmployeeLogin.html')

def StudentLoginAction(request):
    if request.method == 'POST':
        global uname
        username = request.POST.get('t1')
        password = request.POST.get('t2')
        
        con = get_db_connection()
        with con:
            cur = con.cursor()
            cur.execute("select * from student where student_id=%s and password=%s", (username, password))
            if cur.fetchone():
                uname = username
                # --- FIX: Use redirect instead of calling the function ---
                return redirect('StudentScreen')
        
        return render(request, 'StudentLogin.html', {'data': 'login failed'})
    return render(request, 'StudentLogin.html')

def AddEmployeeAction(request):
    if request.method == 'POST':
        data = [request.POST.get(f't{i}') for i in range(1, 10)]
        try:
            con = get_db_connection()
            with con:
                cur = con.cursor()
                cur.execute("select * from employees where username=%s", (data[7],))
                if cur.fetchone():
                    status = "Username already exists"
                else:
                    cur.execute("insert into employees values(%s,%s,%s,%s,%s,%s,%s,%s,%s)", tuple(data))
                    con.commit()
                    status = f"Employee added as {data[6]}"
        except Exception as e:
            status = f"Error: {e}"
        return render(request, 'AddEmployee.html', {'data': status})
    return render(request, 'AddEmployee.html')

def ViewEmployees(request):
    employees = []
    try:
        con = get_db_connection()
        with con:
            cur = con.cursor()
            cur.execute("select * from employees")
            employees = cur.fetchall()
    except Exception as e:
        print(e)
    return render(request, 'ViewEmployees.html', {'employees': employees})

def UpdateEmployeeForm(request):
    username = request.GET.get('username')
    if username:
        con = get_db_connection()
        with con:
            cur = con.cursor()
            cur.execute("select * from employees where username=%s", (username,))
            data = cur.fetchone()
        if data:
            return render(request, 'UpdateEmployee.html', {'employee': data})
    return render(request, 'ViewEmployees.html')

def UpdateEmployeeAction(request):
    if request.method == 'POST':
        old_user = request.POST.get('old_username')
        data = [request.POST.get(f't{i}') for i in range(1, 10)]
        data.append(old_user) 
        try:
            con = get_db_connection()
            with con:
                cur = con.cursor()
                sql = "update employees set emp_name=%s, gender=%s, contact_no=%s, email=%s, qualification=%s, experience=%s, user_role=%s, username=%s, password=%s where username=%s"
                cur.execute(sql, tuple(data))
                con.commit()
            return ViewEmployees(request)
        except Exception as e:
            return render(request, 'ViewEmployees.html', {'data': f'Error: {e}'})
    return ViewEmployees(request)

def DeleteEmployeeAction(request):
    username = request.POST.get('username')
    try:
        con = get_db_connection()
        with con:
            cur = con.cursor()
            cur.execute("delete from employees where username=%s", (username,))
            con.commit()
    except Exception as e:
        print(e)
    return ViewEmployees(request)

def AddStudentAction(request):
    if request.method == 'POST':
        d = [request.POST.get(f't{i}') for i in range(13)] 
        
        try:
            con = get_db_connection()
            with con:
                cur = con.cursor()
                cur.execute("select * from student where student_id=%s and course_year=%s", (d[0], d[6]))
                if cur.fetchone():
                    status = "Student already exists for this year"
                else:
                    sql = "insert into student values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
                    fees = []
                    for i in [7, 9, 10, 11, 12]:
                        try:
                            fees.append(float(d[i]))
                        except:
                            fees.append(0.0)
                    # 14 cols: id, name, gender, contact, email, address, course, year, pass, lib, hostel, tuition, exam, lab
                    values = (d[0], d[1], d[2], d[3], d[4], 'NA', d[5], d[6], d[8], fees[1], fees[2], fees[0], fees[3], fees[4])
                    cur.execute(sql, values)
                    con.commit()
                    status = "Student Added Successfully"
        except Exception as e:
            status = f"Error: {e}"
        return render(request, 'AddStudent.html', {'data': status})
    return render(request, 'AddStudent.html')

def ViewStudents(request):
    global dept
    student_data = []
    try:
        con = get_db_connection()
        with con:
            cur = con.cursor()
            cur.execute("select * from student ORDER BY student_id ASC")
            rows = cur.fetchall()
            
            for row in rows:
                s_id = row[0]
                year = row[7]
                
                total = getTotalFee(s_id, year)
                paid = getPaidFee(s_id, year)
                
                total_sum = sum(total)
                paid_sum = sum(paid)
                due_sum = max(0, total_sum - paid_sum)
                
                # Detailed breakdown strings (Total/Paid)
                lib_str = f"{total[0]}/{paid[0]}"
                hos_str = f"{total[1]}/{paid[1]}"
                tut_str = f"{total[2]}/{paid[2]}"
                exm_str = f"{total[3]}/{paid[3]}"
                lab_str = f"{total[4]}/{paid[4]}"
                
                student_info = {
                    'id': row[0], 'name': row[1], 'contact': row[3], 'email': row[4], 
                    'course': row[6], 'year': row[7],
                    'total_fee': total_sum, 'paid_fee': paid_sum, 'due_fee': due_sum,
                    'lib': lib_str, 'hos': hos_str, 'tut': tut_str, 'exm': exm_str, 'lab': lab_str
                }
                student_data.append(student_info)
                
    except Exception as e:
        print(f"Error fetching students: {e}")
        
    link = '/EmployeeScreen.html' if dept else '/AdminScreen.html'
    return render(request, 'ViewStudents.html', {'students': student_data, 'dashboard_link': link})

def UpdateStudentForm(request):
    sid = request.GET.get('student_id')
    year = request.GET.get('course_year')
    con = get_db_connection()
    with con:
        cur = con.cursor()
        cur.execute("select * from student where student_id=%s and course_year=%s", (sid, year))
        data = cur.fetchone()
    return render(request, 'UpdateStudent.html', {'student': data})

def UpdateStudentAction(request):
    if request.method == 'POST':
        old_id = request.POST.get('old_student_id')
        old_yr = request.POST.get('old_course_year')
        d = [request.POST.get(f't{i}') for i in range(13)]
        values = [d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[8], d[9], d[10], d[7], d[11], d[12], old_id, old_yr]
        try:
            con = get_db_connection()
            with con:
                cur = con.cursor()
                sql = "update student set student_id=%s, student_name=%s, gender=%s, contact_no=%s, email=%s, course=%s, course_year=%s, password=%s, library_fee=%s, hostel_fee=%s, tution_fee=%s, exam_fee=%s, lab_hod_fee=%s where student_id=%s and course_year=%s"
                cur.execute(sql, tuple(values))
                con.commit()
        except Exception as e:
            print(e)
        return ViewStudents(request)
    return ViewStudents(request)

def DeleteStudentAction(request):
    sid = request.POST.get('student_id')
    year = request.POST.get('course_year')
    con = get_db_connection()
    with con:
        cur = con.cursor()
        cur.execute("delete from student where student_id=%s and course_year=%s", (sid, year))
        con.commit()
    return ViewStudents(request)

def AcceptFee(request):
    global dept
    students = []
    con = get_db_connection()
    with con:
        cur = con.cursor()
        cur.execute("select distinct student_id from student")
        for r in cur.fetchall(): students.append(r[0])
    
    labels = {
        "Accounts": "Tution Fee", "Library": "Library Fee", "Hostel": "Hostel Fee",
        "Exam Fee Dept": "Exam Fee", "HOD Lab Returns": "Lab Returns HOD Fee"
    }
    
    return render(request, 'AcceptFee.html', {'students': students, 'dept': dept, 'fee_label': labels.get(dept, 'Fee')})

def AcceptFeeAction(request):
    if request.method == 'POST':
        global dept
        student = request.POST.get('t1')
        fee = request.POST.get('t2')
        year = request.POST.get('t3')
        
        try:
            con = get_db_connection()
            with con:
                cur = con.cursor()
                cur.execute("select * from student where student_id=%s and course_year=%s", (student, year))
                if not cur.fetchone():
                    return render(request, 'EmployeeScreen.html', {'data': 'Student not found'})
                
                cur.execute("insert into payments values(%s,%s,%s,%s,%s)", (student, year, dept, fee, str(date.today())))
                con.commit()
                
                name, pdf = get_fee_receipt(student, dept, fee, str(date.today()))
                response = HttpResponse(pdf, content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="{name}"'
                return response
        except Exception as e:
            return render(request, 'EmployeeScreen.html', {'data': f'Error: {e}'})
    return AcceptFee(request)


def get_fee_receipt(student_id, department, amount, date_str):
    """Generates a Professional Fee Receipt PDF"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.75*inch, leftMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)
    elements = []
    styles = getSampleStyleSheet()
    
    # Try to load logo
    current_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(current_dir, 'static', 'css', 'logo_red.png')
    if os.path.exists(logo_path):
        logo = RLImage(logo_path, width=2*inch, height=0.5*inch, kind='proportional')
        elements.append(logo)
    
    elements.append(Spacer(1, 0.1*inch))
    elements.append(Paragraph("VISHNU INSTITUTE OF TECHNOLOGY", ParagraphStyle('H1', parent=styles['Heading1'], alignment=TA_CENTER, fontSize=18, textColor=HexColor('#1a237e'))))
    elements.append(Paragraph("OFFICIAL FEE RECEIPT", ParagraphStyle('H2', parent=styles['Heading2'], alignment=TA_CENTER, fontSize=14, spaceAfter=20)))
    elements.append(Spacer(1, 0.2*inch))
    
    receipt_no = hashlib.sha256((str(student_id) + str(date_str) + str(department)).encode()).hexdigest()[:10].upper()
    data = [
        ["Receipt No:", receipt_no], 
        ["Transaction Date:", str(date_str)], 
        ["Student ID:", str(student_id)], 
        ["Department:", str(department)], 
        ["Payment Mode:", "Online / Credit Card"], 
        ["Amount Paid:", f"Rs. {amount}/-"], 
        ["Payment Status:", "SUCCESSFUL"]
    ]
    
    t = Table(data, colWidths=[2.5*inch, 3*inch])
    t.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'), ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (0,-1), HexColor('#f2f2f2')), ('TEXTCOLOR', (0,0), (0,-1), HexColor('#1a237e')),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.5*inch))
    
    note_style = ParagraphStyle('Note', parent=styles['Normal'], fontSize=10, textColor=colors.black, alignment=TA_CENTER)
    elements.append(Paragraph(f"This document confirms that <b>{student_id}</b> has cleared the dues for <b>{department}</b>.", note_style))
    
    doc.build(elements)
    pdf_data = buffer.getvalue()
    buffer.close()
    return f"Receipt_{student_id}_{department}.pdf", pdf_data

def ViewPayments(request):
    global dept
    students = []
    con = get_db_connection()
    with con:
        cur = con.cursor()
        cur.execute("select distinct student_id from student")
        for r in cur.fetchall(): students.append(r[0])
    
    link = '/EmployeeScreen.html' if dept else '/AdminScreen.html'
    return render(request, 'ViewPayments.html', {'students': students, 'dashboard_link': link})

def ViewPaymentAction(request):
    global dept
    student = request.POST.get('t1')
    payments = []
    student_list = []
    
    con = get_db_connection()
    with con:
        cur = con.cursor()
        cur.execute("select distinct student_id from student")
        for r in cur.fetchall(): student_list.append(r[0])
        
        query = "select * from payments where student_id=%s"
        params = [student]
        if dept:
            query += " and paying_dept=%s"
            params.append(dept)
        query += " order by payment_date desc"
        
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        
        for row in rows:
            s_id, yr, dpt, amt, dt = row
            total = getDepartmentTotalFee(s_id, yr, dpt)
            paid = getCumulativePaidAmount(s_id, yr, dpt, dt)
            rem = max(0.0, total - paid)
            payments.append(row + (round(rem, 2), rem <= 0))
            
    link = '/EmployeeScreen.html' if dept else '/AdminScreen.html'
    return render(request, 'ViewPayments.html', {
        'students': student_list, 'payments': payments, 'selected_student': student, 'dashboard_link': link
    })

def UpdateFee(request):
    global dept
    students = []
    con = get_db_connection()
    with con:
        cur = con.cursor()
        cur.execute("select distinct student_id from student")
        for r in cur.fetchall(): students.append(r[0])
    
    labels = {
        "Accounts": "Tution Fee", "Library": "Library Fee", "Hostel": "Hostel Fee",
        "Exam Fee Dept": "Exam Fee", "HOD Lab Returns": "Lab Returns HOD Fee"
    }
    
    return render(request, 'UpdateFee.html', {'students': students, 'dept': dept, 'fee_label': labels.get(dept, 'Fee')})

def UpdateFeeAction(request):
    global dept
    student = request.POST.get('t1')
    fee = request.POST.get('t2')
    year = request.POST.get('t3')
    
    cols = {
        "Accounts": "tution_fee", "Library": "library_fee", "Hostel": "hostel_fee",
        "Exam Fee Dept": "exam_fee", "HOD Lab Returns": "lab_hod_fee"
    }
    
    try:
        col = cols.get(dept)
        if not col: return render(request, 'EmployeeScreen.html', {'data': 'Invalid Dept'})
        
        con = get_db_connection()
        with con:
            cur = con.cursor()
            sql = f"update student set {col}=%s where student_id=%s and course_year=%s"
            cur.execute(sql, (fee, student, year))
            con.commit()
            if cur.rowcount > 0:
                msg = "Fee updated"
            else:
                msg = "Student not found"
    except Exception as e:
        msg = f"Error: {e}"
    return render(request, 'EmployeeScreen.html', {'data': msg})

def GenerateNoDue(request):
    global uname
    return render(request, 'GenerateNoDue.html', {'student_id': uname})

def GenerateNoDueAction(request):
    # Declare globals at the very top of the function
    global uname, student_year, student_name_global, student_course_global, cleared, df

    if request.method == 'POST':
        student = request.POST.get('t1')
        year = request.POST.get('t2')
        
        # Update Globals
        uname = student
        student_year = year
        student_name_global, student_course_global = getStudentDetails(student, year)
        
        total = getTotalFee(student, year)
        paid = getPaidFee(student, year)
        
        labels = ["Library Fee", "Hostel Fee", "Tution Fee", "Exam Fee", "Lab Returns HOD Fee"]
        mapping = [0, 1, 2, 3, 4] 
        
        output = f'Student: {student}<br>Year: {year}<br><br><table border=1><tr><th>Type</th><th>Total</th><th>Paid</th><th>Status</th></tr>'
        
        df = [["Student Id", student, f"Year: {year}", "Signed"]]
        all_clear = True
        
        for i in range(5):
            t_amt = total[mapping[i]]
            p_amt = paid[mapping[i]]
            
            status = "Cleared" if (t_amt == 0 or p_amt >= t_amt) else "Not Cleared"
            color = "green" if status == "Cleared" else "red"
            
            if status == "Not Cleared": 
                all_clear = False
                
            output += f'<tr><td>{labels[i]}</td><td>{t_amt}</td><td>{p_amt}</td><td><font color="{color}">{status}</font></td></tr>'
            df.append([labels[i], t_amt, p_amt, status])
            
        output += "</table>"
        cleared = "yes" if all_clear else "no"
        
        if all_clear:
            notify_student(student, "Clearance Successful", "Your No Due Certificate has been generated and is ready for download.")
        
        return render(request, 'StudentScreen.html', {'data': output, 'is_cleared': cleared})

    # GET Request: Use the global uname safely
    student_id_value = uname if uname else ''
    return render(request, 'GenerateNoDue.html', {'student_id': student_id_value})

def Download(request):
    global uname, student_year, df, cleared, student_name_global, student_course_global
    download_type = request.GET.get('type', 'certificate')  # 'certificate', 'qr', or 'both'
    
    if cleared != "yes":
        return render(request, 'StudentScreen.html', {'data': "Dues Not Cleared"})
    
    # Get student details if not already stored
    if not student_name_global or not student_course_global or not student_year:
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
        name, pdf = getCertificate(uname, student_name_global, student_course_global, student_year, df)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{name}"'
        return response

def StudentScreen(request):
    if request.method == 'GET':
        global uname
        if not uname:
             return render(request, 'StudentLogin.html', {})
             
        student_data = []
        try:
            con = get_db_connection()
            with con:
                cur = con.cursor()
                cur.execute("select * from student where student_id=%s ORDER BY course_year DESC", (uname,))
                rows = cur.fetchall()
                
                for row in rows:
                    s_id = row[0]
                    year = row[7]
                    total = getTotalFee(s_id, year) 
                    paid = getPaidFee(s_id, year)
                    
                    fee_details = []
                    dept_names = ["Library", "Hostel", "Accounts (Tuition)", "Exam Branch", "HOD Lab"]
                    
                    for i in range(5):
                        t = total[i]
                        p = paid[i]
                        d = max(0.0, t - p)
                        status = "Cleared" if (t > 0 and d <= 0) or (t==0) else "Pending"
                        color = "green" if status == "Cleared" else "red"
                        
                        fee_details.append({'dept': dept_names[i], 'total': t, 'paid': p, 'due': d, 'status': status, 'color': color})
                    
                    student_data.append({'info': row, 'fees': fee_details})
        except Exception as e:
            print(f"Error in StudentScreen: {e}")

        return render(request, 'StudentScreen.html', {'student_data': student_data, 'uname': uname})

def StudentPayDues(request):
    global uname
    student_id = uname
    year = ""
    dues_context = {}
    has_dues = False
    
    try:
        con = get_db_connection()
        with con:
            cur = con.cursor()
            cur.execute("select course_year from student where student_id=%s ORDER BY course_year DESC LIMIT 1", (student_id,))
            row = cur.fetchone()
            if row: year = row[0]
            
        if year:
            total = getTotalFee(student_id, year)
            paid = getPaidFee(student_id, year)
            depts = {'Library': (0, 0), 'Hostel': (1, 1), 'Accounts': (2, 2), 'Exam Fee Dept': (3, 3), 'HOD Lab Returns': (4, 4)}
            
            for d_name, idxs in depts.items():
                t_idx, p_idx = idxs
                pending = max(0.0, total[t_idx] - paid[p_idx])
                if pending > 0:
                    dues_context[d_name] = {'total': total[t_idx], 'paid': paid[p_idx], 'pending': pending}
                    has_dues = True
    except Exception as e:
        print(e)
        
    return render(request, 'StudentPayDues.html', {'dues': dues_context, 'has_dues': has_dues, 'student_id': student_id, 'year': year})

def StudentPayDuesAction(request):
    if request.method == 'POST':
        student = request.POST.get('student_id')
        year = request.POST.get('year')
        dept = request.POST.get('department')
        amount = request.POST.get('amount')
        try:
            con = get_db_connection()
            with con:
                cur = con.cursor()
                cur.execute("insert into payments values(%s,%s,%s,%s,%s)", (student, year, dept, amount, str(date.today())))
                con.commit()
            
            # Generate and Download Receipt
            name, pdf = get_fee_receipt(student, dept, amount, str(date.today()))
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{name}"'
            return response
        except Exception as e:
            return render(request, 'StudentScreen.html', {'data': f'Error: {e}'})
    return redirect('StudentScreen')
    

def UploadDocument(request):
    global uname
    if request.method == 'POST':
        student = request.POST.get('student_id')
        dept = request.POST.get('department')
        
        if 'document' not in request.FILES: 
            return render(request, 'StudentScreen.html', {'data': 'No File'})
        
        f = request.FILES['document']
        
        # --- CHANGE START: Save to 'documents' subfolder ---
        fs = FileSystemStorage()
        # This saves the file as "documents/filename.pdf"
        fname = fs.save('documents/' + f.name, f)
        fpath = fs.path(fname)
        # --- CHANGE END ---
        
        exp_cat = "irrelevant document"
        if dept == "Accounts": exp_cat = "tuition fee receipt"
        elif dept == "Library": exp_cat = "library no due certificate"
        elif dept == "Hostel": exp_cat = "hostel clearance form"
        
        valid, conf, msg = analyze_document_content(fpath, exp_cat)
        status = "Cleared" if valid else "Rejected"
        
        try:
            con = get_db_connection()
            with con:
                cur = con.cursor()
                # Store the relative path (fname) in the database
                cur.execute("insert into document_submissions(student_id, department, file_path, ai_verification_status, ai_confidence_score) values(%s,%s,%s,%s,%s)", 
                            (student, dept, fname, status, conf))
                
                if valid:
                    cur.execute("select course_year from student where student_id=%s order by course_year desc limit 1", (student,))
                    row = cur.fetchone()
                    if row:
                        yr = row[0]
                        col = ""
                        if dept == "Accounts": col = "tution_fee"
                        elif dept == "Library": col = "library_fee"
                        elif dept == "Hostel": col = "hostel_fee"
                        
                        if col:
                            cur.execute(f"update student set {col}=0 where student_id=%s and course_year=%s", (student, yr))
                con.commit()
                
            final_msg = f"AI Verification Success ({conf:.2f})" if valid else f"AI Failed: {msg}"
            return render(request, 'StudentScreen.html', {'data': final_msg})
            
        except Exception as e:
            return render(request, 'StudentScreen.html', {'data': f"Error: {str(e)}"})
            
    return render(request, 'UploadDocument.html', {'student_id': uname})

def AdminScreen(request):
    global uname
    return render(request, 'AdminScreen.html', {'data': f'welcome {uname}'})

def EmployeeScreen(request):
    global uname
    return render(request, 'EmployeeScreen.html', {'data': f'welcome {uname}'})

def ScanQR(request):
    return render(request, 'ScanQR.html')

def VerifyCertificate(request):
    if request.method == 'GET':
        student_id = request.GET.get('student_id', '')
        year = request.GET.get('year', '')
        
        if not student_id or not year:
            return JsonResponse({'success': False, 'message': 'Student ID and Year are required'})
        
        try:
            student_name, course = getStudentDetails(student_id, year)
            con = get_db_connection()
            with con:
                cur = con.cursor()
                cur.execute("select * from student where student_id=%s and course_year=%s", (student_id, year))
                if not cur.fetchone():
                    return JsonResponse({'success': False, 'message': 'Student not found'})
            
            total = getTotalFee(student_id, year)
            paid = getPaidFee(student_id, year)
            
            all_cleared = True
            for i in range(5):
                if not (total[i] == 0 or paid[i] >= total[i]):
                    all_cleared = False
                    break
            
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
            student_name, course = getStudentDetails(student_id, year)
            total = getTotalFee(student_id, year)
            paid = getPaidFee(student_id, year)
            
            labels = ["Library Fee", "Hostel Fee", "Tution Fee", "Exam Fee", "Lab Returns HOD Fee"]
            fee_data = [["Student Id", student_id, f"Year: {year}", "Signed"]]
            
            for i in range(5):
                t_amt = total[i]
                p_amt = paid[i]
                status = "Cleared" if (t_amt == 0 or p_amt >= t_amt) else "Not Cleared"
                fee_data.append([labels[i], t_amt, p_amt, status])
            
            name, pdf = getCertificate(student_id, student_name, course, year, fee_data)
            
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{name}"'
            return response
            
        except Exception as e:
            return HttpResponse('Error generating certificate: ' + str(e), status=500)

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
    



def notify_student(student_id, subject, message):
    """Fetches student email from DB and sends a notification."""
    email = ""
    try:
        # Connect to your database
        con = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='root', database='nodue_new', charset='utf8')
        with con:
            cur = con.cursor()
            cur.execute("select email from student where student_id=%s", (student_id,))
            row = cur.fetchone()
            if row and row[0]:
                email = row[0]
        
        if email:
            # Configure your email settings here
            msg = f"Subject: {subject}\n\n{message}"
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as connection:
                email_address = 'kaleem202120@gmail.com'  # Your email
                email_password = 'xyljzncebdxcubjq'       # Your app password
                connection.login(email_address, email_password)
                connection.sendmail(from_addr=email_address, to_addrs=[email], msg=msg)
                print(f"Email sent successfully to {email}")
    except Exception as e:
        print(f"Error sending email: {e}")



        # end of the code ne push orking check

