from werkzeug.security import generate_password_hash, check_password_hash
import csv
import io
from flask import Response
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename
import requests # <--- NUEVO: Para comunicarnos con Supabase
import uuid     # <--- NUEVO: Para que las fotos tengan nombres únicos

app = Flask(__name__)

# --- CONFIGURACIÓN DE SEGURIDAD Y BASE DE DATOS ---
# --- CONFIGURACIÓN DE SEGURIDAD Y BASE DE DATOS ---
app.secret_key = os.environ.get("SECRET_KEY", "super_secreta_clave_villa_angela")
app.config['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres.lclcbghsdwwmzqczjkte:cR2WN8Xq18h4Utgn@aws-1-us-east-1.pooler.supabase.com:5432/postgres"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
from datetime import datetime, timedelta

# Generador dinámico de turnos cada 30 minutos
def generar_horarios():
    conf = Configuracion.query.first()
    
    # Si no hay configuración, devolvemos una lista por defecto
    if not conf or not conf.h_inicio_m:
        return ["08:00", "08:30", "09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "16:00", "16:30", "17:00", "17:30", "18:00", "18:30", "19:00", "19:30"]

    horarios = []
    formato = '%H:%M'

    def agregar_rango(inicio_str, fin_str):
        if not inicio_str or not fin_str: return
        try:
            # Cortamos a 5 letras por si viene con segundos ("08:00:00" -> "08:00")
            inicio = datetime.strptime(inicio_str[:5], formato)
            fin = datetime.strptime(fin_str[:5], formato)
            while inicio < fin:
                horarios.append(inicio.strftime(formato))
                inicio += timedelta(minutes=30) # Turnos cada 30 min
        except:
            pass

    agregar_rango(conf.h_inicio_m, conf.h_fin_m)
    agregar_rango(conf.h_inicio_t, conf.h_fin_t)
    
    return horarios

# --- CONEXIÓN A SUPABASE STORAGE ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

BUCKET_NAME = "archivos_clinica"
URL_BASE_FOTOS = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/"

# --- MODELOS ---
class ConfiguracionDia(db.Model):
    __tablename__ = 'configuracion_dia'
    id = db.Column(db.Integer, primary_key=True)
    dia_semana = db.Column(db.Integer)  # 0 = Lunes, 6 = Domingo
    activo = db.Column(db.Boolean, default=True) # ¿Trabaja este día?
    hora_inicio = db.Column(db.String(5), default="09:00")
    hora_fin = db.Column(db.String(5), default="18:00")
    
class Turno(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    dni = db.Column(db.String(20), nullable=False)
    telefono = db.Column(db.String(20), nullable=False)
    direccion = db.Column(db.String(200), nullable=False)
    cobertura = db.Column(db.String(100), nullable=False)
    tratamiento = db.Column(db.String(100), nullable=False)
    fecha = db.Column(db.String(20), nullable=False)
    hora = db.Column(db.String(10), nullable=False)
    odontograma = db.Column(db.JSON, default={})
    
    activo = db.Column(db.Boolean, default=True)
    
    
    # Campos clínicos
    edad = db.Column(db.String(10), nullable=True)
    alergias = db.Column(db.String(200), nullable=True)
    notas = db.Column(db.Text, nullable=True)
    estado_pago = db.Column(db.String(50), default="Pendiente")
    radiografia = db.Column(db.String(100), nullable=True) # <--- NUEVO
    
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow) 

# La clase Configuracion debe ir afuera y separada
class Configuracion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre_clinica = db.Column(db.String(100), default="Consultorio Odontológico")
    color_primario = db.Column(db.String(20), default="#007aff")
    logo_filename = db.Column(db.String(100), nullable=True) # <--- NUEVO
    # Horarios de atención
    h_inicio_m = db.Column(db.String(10), default="08:00")
    h_fin_m = db.Column(db.String(10), default="12:00")
    h_inicio_t = db.Column(db.String(10), default="16:00")
    h_fin_t = db.Column(db.String(10), default="20:00")
    usuario_admin = db.Column(db.String(50), default="admin")
    password_hash = db.Column(db.String(255), nullable=True)
    
class Cierre(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.String(10), unique=True, nullable=False)    

with app.app_context():
    db.create_all()

# --- RUTAS PWA ---
@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/sw.js')
def service_worker():
    return send_from_directory('static', 'sw.js')

# --- VISTAS PÚBLICAS ---
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/agendar', methods=['GET', 'POST'])
def agendar():
    # Si el paciente solo está entrando a la página para ver el formulario:
    if request.method == 'GET':
        return render_template('agendar.html')
        
    # Si el paciente apretó el botón "Confirmar" (POST):
    dni = request.form.get('dni')
    fecha = request.form.get('fecha')
    hora = request.form.get('hora')
    hoy = datetime.now().strftime('%Y-%m-%d')

    # REGLA 1: ¿El paciente ya tiene un turno pendiente?
    turno_existente = Turno.query.filter(Turno.dni == dni, Turno.fecha >= hoy).first()
    if turno_existente:
        return "Ya tenés un turno agendado para el " + turno_existente.fecha + ". Por favor, reprogramalo si necesitás otro horario."

    # REGLA 2: Doble verificación de seguridad (Evitar turnos dobles)
    ocupado = Turno.query.filter_by(fecha=fecha, hora=hora).first()
    if ocupado:
        return "Lo sentimos, alguien acaba de reservar ese horario. Por favor, elegí otro."

    # Si pasa las reglas, guardamos
    nuevo_turno = Turno(
        nombre=request.form.get('nombre'),
        dni=dni,
        telefono=request.form.get('telefono'),
        cobertura=request.form.get('cobertura'),
        tratamiento=request.form.get('tratamiento'),
        fecha=fecha,
        hora=hora,
        edad=request.form.get('edad'),
        alergias=request.form.get('alergias')
    )
    
    try:
        db.session.add(nuevo_turno)
        db.session.commit()
        return render_template('confirmacion.html', turno=nuevo_turno)
    except:
        db.session.rollback()
        return "Hubo un error al procesar tu turno. Intentá de nuevo."

@app.route('/guardar_turno', methods=['POST'])
def guardar_turno():
    dni = request.form.get('dni')
    fecha_elegida = request.form.get('fecha')
    hora_elegida = request.form.get('hora')
    hoy = datetime.utcnow().strftime('%Y-%m-%d')

    # 1. BUSCAR SI EL PACIENTE YA TIENE UN TURNO PENDIENTE
    turno_previo = Turno.query.filter(Turno.dni == dni, Turno.fecha >= hoy).first()
    if turno_previo:
        return render_template('agendar.html', 
            error=f"Ya tenés un turno el día {turno_previo.fecha} a las {turno_previo.hora}. Podés pedirle a la doctora que lo modifique o esperar a que pase para sacar uno nuevo.",
            datos=request.form)

    # 2. VALIDACIÓN DE DISPONIBILIDAD
    turno_existente = Turno.query.filter_by(fecha=fecha_elegida, hora=hora_elegida).first()
    if turno_existente:
        return render_template('agendar.html', error="Ese horario ya está reservado.", datos=request.form)

    # Guardado normal
    nuevo_turno = Turno(
        nombre=request.form.get('nombre'), dni=dni, telefono=request.form.get('telefono'),
        direccion=request.form.get('direccion'), cobertura=request.form.get('nombre_os') or "Particular",
        tratamiento=request.form.get('tratamiento'), fecha=fecha_elegida, hora=hora_elegida,
        edad=request.form.get('edad'), alergias=request.form.get('alergias')
    )
    db.session.add(nuevo_turno)
    db.session.commit()
    
    # Preparamos el link de WhatsApp limpio sin romper Python
    numero_doctora = "5493735417513"
    mensaje_ws = f"Hola! Soy {nuevo_turno.nombre}. Acabo de agendar un turno para {nuevo_turno.tratamiento} el día {nuevo_turno.fecha} a las {nuevo_turno.hora} hs."
    mensaje_enlace = mensaje_ws.replace(" ", "%20")

    # Retornamos directamente el ticket visual
    return f"""
    <div style="font-family: system-ui; padding: 20px; max-width: 500px; margin: 0 auto; background: #f2f2f7; min-height: 100vh; display: flex; align-items: center;">
        <div style="background: white; padding: 30px; border-radius: 28px; box-shadow: 0 10px 30px rgba(0,0,0,0.08); text-align: center; width: 100%;">
            <div style="font-size: 50px; margin-bottom: 20px;">✅</div>
            <h2 style="margin: 0 0 10px 0; color: #1c1c1e;">¡Turno Confirmado!</h2>
            <p style="color: #8e8e93; margin-bottom: 25px;">Tu lugar ya está reservado en la agenda.</p>
            
            <div style="background: #f9f9f9; padding: 15px; border-radius: 16px; text-align: left; margin-bottom: 25px; border: 1px solid #eee;">
                <p style="margin: 5px 0;"><strong>Fecha:</strong> {nuevo_turno.fecha}</p>
                <p style="margin: 5px 0;"><strong>Hora:</strong> {nuevo_turno.hora} hs</p>
            </div>

            <a href="https://wa.me/{numero_doctora}?text={mensaje_enlace}" 
               style="display: flex; align-items: center; justify-content: center; gap: 10px; background: #25D366; color: white; padding: 16px; text-decoration: none; border-radius: 14px; font-weight: 700; margin-bottom: 12px; box-shadow: 0 4px 12px rgba(37,211,102,0.3);">
               <span>Avisar por WhatsApp</span>
            </a>

            <a href="/" style="display: block; color: #007aff; text-decoration: none; font-weight: 600; padding: 10px;">Finalizar</a>
        </div>
    </div>
    """

# --- API PÚBLICA DE DISPONIBILIDAD ---
@app.route('/api/disponibilidad/<fecha>')
def disponibilidad(fecha):
    dia_cerrado = Cierre.query.filter_by(fecha=fecha).first()
    
    if dia_cerrado:
        # Si el día está bloqueado, marcamos todos los horarios del día como ocupados
        return jsonify(generar_horarios())

    turnos_del_dia = Turno.query.filter_by(fecha=fecha).all()
    horas_ocupadas = [turno.hora for turno in turnos_del_dia]
    
    return jsonify(horas_ocupadas)

    # 2. Si el día está abierto, buscamos las horas ocupadas normalmente
    turnos_del_dia = Turno.query.filter_by(fecha=fecha).all()
    horas_ocupadas = [turno.hora for turno in turnos_del_dia]
    
    return jsonify(horas_ocupadas)

# --- SISTEMA DE LOGIN Y SEGURIDAD ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        usuario_ingresado = request.form.get('usuario')
        contrasena_ingresada = request.form.get('contrasena')
        
        conf = Configuracion.query.first()
        
        # MAGIA 1: Si es la primera vez y la contraseña está vacía, le ponemos '12345' encriptada por defecto
        if not conf.password_hash:
            conf.password_hash = generate_password_hash('12345')
            db.session.commit()
            
        # MAGIA 2: Comparamos el usuario y verificamos si la contraseña coincide con el código encriptado
        if usuario_ingresado == conf.usuario_admin and check_password_hash(conf.password_hash, contrasena_ingresada):
            session['logeado'] = True 
            return redirect(url_for('panel'))
        else:
            error = "Usuario o contraseña incorrectos."
            
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logeado', None) 
    return redirect(url_for('home'))

# --- PANEL DE CONTROL ---
@app.route('/panel')
def panel():
    if not session.get('logeado'):
        return redirect(url_for('login'))
    
    lista_turnos = Turno.query.filter_by(activo=True).order_by(Turno.fecha, Turno.hora).all()
    return render_template('panel.html', turnos=lista_turnos)

# --- NUEVAS RUTAS PARA EL CALENDARIO ---
@app.route('/api/turnos')
def api_turnos():
    if not session.get('logeado'):
        return jsonify({'error': 'No autorizado'}), 403
    
    turnos = Turno.query.filter_by(activo=True).all()
    lista = []
    for t in turnos:
        lista.append({
            'id': t.id,
            'nombre': t.nombre,
            'telefono': t.telefono,
            'tratamiento': t.tratamiento,
            'fecha': t.fecha, 
            'hora': t.hora,
            'cobertura': t.cobertura
        })
    return jsonify(lista)

@app.route('/eliminar_turno/<int:id>', methods=['POST'])
def eliminar_turno(id):
    if not session.get('logeado'): return redirect(url_for('login'))
    
    turno = Turno.query.get_or_404(id)
    turno.activo = False # <--- Apagamos en vez de borrar
    db.session.commit()
    return redirect(url_for('panel'))

@app.route('/reprogramar_turno/<int:id>', methods=['POST'])
def reprogramar_turno(id):
    if not session.get('logeado'):
        return redirect(url_for('login'))
    
    turno = Turno.query.get_or_404(id)
    nueva_fecha = request.form.get('nueva_fecha')
    nueva_hora = request.form.get('nueva_hora')
    
    if nueva_fecha and nueva_hora:
        turno.fecha = nueva_fecha
        turno.hora = nueva_hora
        db.session.commit()
    
    return redirect(url_for('panel'))

# --- NUEVA SECCIÓN: PACIENTES Y HISTORIAL ---
@app.route('/pacientes')
def pacientes():
    if not session.get('logeado'):
        return redirect(url_for('login'))
    
    todos_los_turnos = Turno.query.filter_by(activo=True).order_by(Turno.nombre).all()
    pacientes_dict = {}
    for t in todos_los_turnos:
        if t.dni not in pacientes_dict:
            pacientes_dict[t.dni] = {
                'nombre': t.nombre,
                'dni': t.dni,
                'telefono': t.telefono,
                'direccion': t.direccion,
                'cobertura': t.cobertura
            }
    
    lista_pacientes = list(pacientes_dict.values())
    return render_template('pacientes.html', pacientes=lista_pacientes)

@app.route('/api/historial/<dni>')
def api_historial(dni):
    if not session.get('logeado'):
        return jsonify({'error': 'No autorizado'}), 403
        
    turnos_paciente = Turno.query.filter_by(dni=dni, activo=True).order_by(Turno.fecha.desc(), Turno.hora.desc()).all()
    
    # 🇦🇷 Ajustamos la hora al horario de Argentina (UTC-3)
    ahora = datetime.utcnow() - timedelta(hours=3)
    hoy_str = ahora.strftime('%Y-%m-%d')
    hora_actual_str = ahora.strftime('%H:%M')
    
    lista = []
    for t in turnos_paciente:
        # Lógica inteligente: Es "Pasado" si la fecha ya pasó 
        # O si es hoy pero la hora ya pasó
        if t.fecha < hoy_str:
            estado = "Pasado"
        elif t.fecha == hoy_str and t.hora <= hora_actual_str:
            estado = "Pasado"
        else:
            estado = "Proximo"
            
        foto_url = f"{URL_BASE_FOTOS}{t.radiografia}" if t.radiografia else None
        
        lista.append({
            'id': t.id, 'tratamiento': t.tratamiento, 'fecha': t.fecha, 'hora': t.hora, 
            'estado': estado, 'edad': t.edad, 'alergias': t.alergias, 
            'notas': t.notas or '', 'estado_pago': t.estado_pago,
            'radiografia': foto_url, 'nombre': t.nombre,
            'telefono': t.telefono, 'cobertura': t.cobertura,
            'odontograma': t.odontograma
        })
    return jsonify(lista)

@app.route('/actualizar_ficha/<int:id>', methods=['POST'])
def actualizar_ficha(id):
    if not session.get('logeado'):
        return redirect(url_for('login'))
    
    turno = Turno.query.get_or_404(id)
    turno.notas = request.form.get('notas')
    
    # Asegurarnos de guardar el estado de pago (y la deuda si existe)
    estado_pago = request.form.get('estado_pago')
    if estado_pago:
        turno.estado_pago = estado_pago
        
    monto_deuda = request.form.get('monto_deuda')
    if monto_deuda:
        turno.monto_deuda = monto_deuda
    
    # --- NUEVA LÓGICA PARA RADIOGRAFÍAS MÚLTIPLES (CARRUSEL) ---
    fotos = request.files.getlist('radiografias')
    nuevas_urls = []
    
    for foto in fotos:
        if foto and foto.filename != '':
            extension = foto.filename.split('.')[-1]
            nombre_unico = f"radio_{turno.id}_{uuid.uuid4().hex}.{extension}"
            
            # 1. URL para SUBIR a Supabase (ruta interna)
            url_upload = f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{nombre_unico}"
            headers = {
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "apikey": SUPABASE_KEY,
                "Content-Type": foto.content_type
            }
            
            respuesta = requests.post(url_upload, headers=headers, data=foto.read())
            
            if respuesta.status_code == 200:
                # 2. EL ARREGLO: Armamos la URL PÚBLICA exacta y completa
                url_publica = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/{nombre_unico}"
                nuevas_urls.append(url_publica)

    if nuevas_urls:
        urls_string = ",".join(nuevas_urls)
        # Limpiamos si había alguna coma perdida vieja (.strip)
        if turno.radiografia and turno.radiografia.strip(',') != "":
            turno.radiografia = turno.radiografia.strip(',') + "," + urls_string
        else:
            turno.radiografia = urls_string

    db.session.commit()
    return redirect(url_for('pacientes'))
# NUEVA RUTA: Para eliminar radiografías
@app.route('/eliminar_radiografia/<int:id>', methods=['POST'])
def eliminar_radiografia(id):
    if not session.get('logeado'):
        return jsonify({'error': 'No autorizado'}), 403
    
    turno = Turno.query.get_or_404(id)
    
    if turno.radiografia:
        # Le decimos a Supabase que borre el archivo
        url_delete = f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{turno.radiografia}"
        headers = {
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "apikey": SUPABASE_KEY
        }
        requests.delete(url_delete, headers=headers)
        
        # Vaciamos la columna en la base de datos
        turno.radiografia = None
        db.session.commit()
        
    return jsonify({'success': True})
# --- NUEVAS RUTAS: EDITAR Y ELIMINAR PACIENTE ---
@app.route('/editar_paciente/<dni>', methods=['POST'])
def editar_paciente(dni):
    if not session.get('logeado'): return redirect(url_for('login'))
    
    turnos = Turno.query.filter_by(dni=dni).all()
    for t in turnos:
        t.nombre = request.form.get('nombre')
        t.telefono = request.form.get('telefono')
        t.cobertura = request.form.get('cobertura')
        t.edad = request.form.get('edad')
        t.alergias = request.form.get('alergias')
        
    db.session.commit()
    return redirect(url_for('pacientes'))

@app.route('/eliminar_paciente/<dni>', methods=['POST'])
def eliminar_paciente(dni):
    if not session.get('logeado'): return redirect(url_for('login'))
    
    turnos = Turno.query.filter_by(dni=dni).all()
    for t in turnos:
        # Borramos las fotos pesadas de Supabase para ahorrar espacio
        if t.radiografia:
            url_delete = f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{t.radiografia}"
            headers = {"Authorization": f"Bearer {SUPABASE_KEY}", "apikey": SUPABASE_KEY}
            requests.delete(url_delete, headers=headers)
            t.radiografia = None
            
        # Apagamos el historial del paciente, pero no destruimos su texto
        t.activo = False
        
    db.session.commit()
    return redirect(url_for('pacientes'))

# --- AJUSTES Y CONFIGURACIÓN ---
@app.context_processor
def inject_config():
    conf = Configuracion.query.first()
    if not conf:
        conf = Configuracion(nombre_clinica="Consultorio Villa Ángela")
        db.session.add(conf)
        db.session.commit()
        
    # ACÁ ESTÁ EL ÚNICO CAMBIO: Le sumamos horarios_base al final del diccionario
    return dict(config=conf, url_fotos=URL_BASE_FOTOS, horarios_base=generar_horarios())

@app.route('/ajustes')
def ajustes():
    # Control de seguridad (login)
    if not session.get('logeado'):
        return redirect(url_for('login'))
    
    # 1. Tu lógica original (Cierres de caja)
    cierres = Cierre.query.all()
    
    # 2. La nueva lógica (Agenda dinámica de la doctora)
    configuraciones = ConfiguracionDia.query.all()
    config_dict = {c.dia_semana: c for c in configuraciones}
    
    # 3. Enviamos ambas variables a la pantalla para evitar el error de Jinja2
    return render_template('ajustes.html', cierres=cierres, config_dict=config_dict)

@app.route('/guardar_ajustes', methods=['POST'])
def guardar_ajustes():
    if not session.get('logeado'): return redirect(url_for('login'))
    conf = Configuracion.query.first()
    conf.nombre_clinica = request.form.get('nombre_clinica')
    conf.color_primario = request.form.get('color_primario')
    conf.h_inicio_m = request.form.get('h_inicio_m')
    conf.h_fin_m = request.form.get('h_fin_m')
    conf.h_inicio_t = request.form.get('h_inicio_t')
    conf.h_fin_t = request.form.get('h_fin_t')

    # Guardar el logo en Supabase
    logo = request.files.get('logo')
    if logo and logo.filename != '':
        extension = logo.filename.split('.')[-1]
        nombre_unico = f"logo_{uuid.uuid4().hex}.{extension}"
        
        # Enviamos el archivo a Supabase
        url_upload = f"{SUPABASE_URL}/storage/v1/object/{BUCKET_NAME}/{nombre_unico}"
        headers = {
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "apikey": SUPABASE_KEY,
            "Content-Type": logo.content_type
        }
        respuesta = requests.post(url_upload, headers=headers, data=logo.read())
        
        if respuesta.status_code == 200:
            conf.logo_filename = nombre_unico
    nuevo_usuario = request.form.get('usuario_admin')
    nueva_pass = request.form.get('nueva_password')
    
    if nuevo_usuario:
        conf.usuario_admin = nuevo_usuario
        
    # Si la doctora escribió algo en "Nueva Contraseña", la encriptamos y la guardamos
    if nueva_pass and nueva_pass.strip() != "":
        conf.password_hash = generate_password_hash(nueva_pass)        

    db.session.commit()
    return redirect(url_for('ajustes'))
# Ruta para que la doctora bloquee un día (en Ajustes)
@app.route('/bloquear_fecha', methods=['POST'])
def bloquear_fecha():
    if not session.get('logeado'): return redirect(url_for('login'))
    
    fecha_inicio = request.form.get('fecha_inicio')
    fecha_fin = request.form.get('fecha_fin')
    
    # Si no pone fecha de fin, asumimos que es solo un día
    if not fecha_fin:
        fecha_fin = fecha_inicio

    if fecha_inicio:
        inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d')
        fin = datetime.strptime(fecha_fin, '%Y-%m-%d')
        delta = timedelta(days=1)
        fecha_actual = inicio
        
        turnos_afectados = 0
        
        # Recorremos todos los días del rango seleccionado
        while fecha_actual <= fin:
            fecha_str = fecha_actual.strftime('%Y-%m-%d')
            
            # 1. Chequeamos si hay pacientes ya agendados ese día
            afectados = Turno.query.filter_by(fecha=fecha_str).count()
            turnos_afectados += afectados
            
            # 2. Bloqueamos el día en la base de datos (si no estaba bloqueado ya)
            existe = Cierre.query.filter_by(fecha=fecha_str).first()
            if not existe:
                nuevo_cierre = Cierre(fecha=fecha_str)
                db.session.add(nuevo_cierre)
                
            fecha_actual += delta
            
        db.session.commit()
        
        # 3. Le avisamos a la doctora el resultado
        if turnos_afectados > 0:
            flash(f"⚠️ ATENCIÓN: Se bloquearon los días, pero hay {turnos_afectados} turno/s que ya estaban agendados en esas fechas. Por favor, revisá el panel de inicio para contactarlos y reprogramarlos.")
        else:
            flash("✅ Días bloqueados correctamente. Nadie podrá sacar turnos en esas fechas.")

    return redirect(url_for('ajustes'))

# Ruta para desbloquear un día
@app.route('/desbloquear_fecha/<int:id>', methods=['POST'])
def desbloquear_fecha(id):
    if not session.get('logeado'): 
        return jsonify({'error': 'No autorizado'}), 403
    
    cierre = Cierre.query.get(id)
    if cierre:
        db.session.delete(cierre)
        db.session.commit()
        
    # En vez de redirigir, devolvemos un JSON para que Javascript borre el recuadro
    return jsonify({'success': True})

@app.route('/api/cantidad_turnos')
def cantidad_turnos():
    if not session.get('logeado'):
        return jsonify({'count': 0})
    hoy = datetime.now().strftime('%Y-%m-%d')
    cantidad = Turno.query.filter(Turno.fecha >= hoy).count()
    return jsonify({'count': cantidad})
@app.route('/api/horarios_base')
def api_horarios_base():
    return jsonify(generar_horarios())

@app.route('/descargar_backup')
def descargar_backup():
    if not session.get('logeado'):
        return redirect(url_for('login'))
    
    # 1. Obtenemos todos los turnos/pacientes activos
    turnos = Turno.query.filter_by(activo=True).order_by(Turno.fecha.desc()).all()
    
    # 2. Creamos un archivo virtual en la memoria del servidor
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 3. Escribimos los encabezados (las columnas del Excel)
    writer.writerow([
        'ID', 'Nombre', 'DNI', 'Telefono', 'Direccion', 'Cobertura', 
        'Tratamiento', 'Fecha', 'Hora', 'Edad', 'Alergias', 'Notas/Evolucion', 'Estado Pago'
    ])
    
    # 4. Cargamos los datos de cada paciente
    for t in turnos:
        writer.writerow([
            t.id, t.nombre, t.dni, t.telefono, t.direccion, t.cobertura,
            t.tratamiento, t.fecha, t.hora, t.edad, t.alergias, t.notas, t.estado_pago
        ])
    
    # 5. Preparamos la respuesta para el navegador
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=backup_clinica_{datetime.now().strftime('%Y%m%d')}.csv"}
    )
    
    # --- RUTA PARA GUARDAR EL ODONTOGRAMA ---
@app.route('/guardar_odontograma/<dni>', methods=['POST'])
def guardar_odontograma(dni):
    try:
        # 1. Recibimos el mapa de los dientes (los colores) desde Javascript
        mapa_dientes = request.json
        
        # 2. Actualizamos TODOS los turnos de este DNI usando SQLAlchemy
        # (Asegurate de que tu clase se llame 'Turno' con T mayúscula, o cambialo si usás minúscula)
        Turno.query.filter_by(dni=dni).update({'odontograma': mapa_dientes})
        db.session.commit() # Guardamos los cambios en la base de datos
        
        return jsonify({'success': True, 'mensaje': 'Odontograma actualizado'})
    except Exception as e:
        db.session.rollback() # Si hay un error, cancelamos la operación para no romper nada
        print(f"Error al guardar odontograma: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/guardar_horario_dia', methods=['POST'])
def guardar_horario_dia():
    datos = request.json
    dia_semana = int(datos['dia_semana']) 
    nuevo_inicio = datos['hora_inicio']   
    nuevo_fin = datos['hora_fin']         
    
    # --- LA CORRECCIÓN ESTÁ ACÁ ---
    # 1. Sacamos la fecha de hoy en formato texto (ej: "2026-04-14")
    hoy_str = datetime.now().strftime('%Y-%m-%d')
    
    # 2. Buscamos TODOS los turnos futuros comparando la fecha, sin usar 'estado'
    turnos_futuros = Turno.query.filter(Turno.fecha >= hoy_str).all()
    
    turnos_afectados = []
    
    # Escaneamos uno por uno como un radar
    for t in turnos_futuros:
        try:
            fecha_obj = datetime.strptime(t.fecha, '%Y-%m-%d')
            if fecha_obj.weekday() == dia_semana:
                # Si el turno es antes de abrir o después de cerrar, salta la alarma
                if t.hora < nuevo_inicio or t.hora >= nuevo_fin:
                    turnos_afectados.append({
                        'paciente': t.nombre,
                        'fecha': t.fecha,
                        'hora': t.hora
                    })
        except ValueError:
            continue # Ignoramos si alguna fecha vieja está mal guardada
    
    # Guardamos la nueva configuración
    config = ConfiguracionDia.query.filter_by(dia_semana=dia_semana).first()
    if not config:
        config = ConfiguracionDia(dia_semana=dia_semana)
        db.session.add(config)
    
    config.hora_inicio = nuevo_inicio
    config.hora_fin = nuevo_fin
    config.activo = datos.get('activo', True)
    db.session.commit()
    
    # Le respondemos a la pantalla
    if len(turnos_afectados) > 0:
        return jsonify({
            'success': True,
            'alerta': True,
            'mensaje': f"Horario guardado. ATENCIÓN: Hay {len(turnos_afectados)} turnos que quedaron fuera del horario.",
            'afectados': turnos_afectados
        })
    else:
        return jsonify({'success': True, 'alerta': False, 'mensaje': "Horario actualizado sin conflictos."})    

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')