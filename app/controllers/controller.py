import datetime
from io import BytesIO
import traceback
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, send_file, send_from_directory, session, url_for
import os
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import extract, func
from app import db
from datetime import datetime, date, time, timedelta
from flask_login import current_user, login_required, login_user, logout_user
from fpdf import FPDF  
from app.models.models import Categoria, DetalleVenta, Gasto, Producto, Usuario, Venta

# Obtiene la ruta absoluta a la carpeta de plantillas dentro del módulo
template_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')

inicio_cp = Blueprint('inicio_cp', __name__, template_folder=template_dir)
usuario_cp = Blueprint('usuario_cp', __name__, template_folder=template_dir)
producto_cp = Blueprint('producto_cp', __name__, template_folder=template_dir)
admin_cp = Blueprint('admin', __name__, template_folder=template_dir)
auth_cp = Blueprint('auth_cp', __name__, template_folder=template_dir)

# -------------------------------
# Rutas de inicio público
# -------------------------------

@inicio_cp.route('/inicio')
def inicio_publico():
    categorias = Categoria.query.all()
    productos_destacados = Producto.query.filter_by(destacado=True).limit(8).all()
    productos_recientes = Producto.query.order_by(Producto.created_at.desc()).limit(8).all()
    
    # Estadísticas para mostrar
    total_productos = Producto.query.count()
    total_categorias = Categoria.query.count()
    total_clientes = Usuario.query.filter_by(is_admin=False).count()
    
    return render_template('auth/inicio.html',
                         categorias=categorias,
                         productos_destacados=productos_destacados,
                         productos=productos_recientes,
                         total_productos=total_productos,
                         total_categorias=total_categorias,
                         total_clientes=total_clientes)
# -------------------------------
# autenticación
# -------------------------------
auth_cp = Blueprint('auth', __name__)

@auth_cp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and usuario.check_password(password):
            login_user(usuario)
            flash('Inicio de sesión exitoso.', 'success')

            # Redirección según rol
            if usuario.is_admin:
                flash('Bienvenido Administrador.', 'info')
                return redirect(url_for('admin.dashboard'))
            else:
                flash('Bienvenido Usuario.', 'info')
                return redirect(url_for('usuario_cp.user_dashboard'))

        # Si el usuario no existe o la contraseña es incorrecta
        flash('Credenciales incorrectas.', 'danger')
        return redirect(url_for('auth.login'))

    # Método GET → mostrar el formulario
    return render_template('auth/login.html')


@auth_cp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if Usuario.query.filter_by(username=username).first():
            flash('El nombre de usuario ya existe.', 'warning')
            return redirect(url_for('auth.register'))

        nuevo_usuario = Usuario(username=username, email=email)
        nuevo_usuario.set_password(password)

        db.session.add(nuevo_usuario)
        db.session.commit()

        flash('Registro exitoso. Ahora puedes iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_cp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Has cerrado sesión.', 'info')
    return redirect(url_for('inicio_cp.inicio_publico'))

@usuario_cp.route('/uploads/productos/<filename>')
def serve_uploaded_file(filename):
    # Ruta absoluta a la carpeta de uploads
    uploads_dir = os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads', 'productos')
    return send_from_directory(uploads_dir, filename)
#-------------------------------
# Rutas de administración
#-------------------------------
@admin_cp.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_admin:
        return redirect(url_for('inicio_cp.inicio_publico'))

    # Datos principales
    total_usuarios = Usuario.query.count()
    total_productos = Producto.query.count()
    total_ventas = db.session.query(func.sum(Venta.total)).scalar() or 0
    
    # Datos adicionales para el nuevo dashboard
    productos_destacados = Producto.query.filter_by(destacado=True).all()
    usuarios_activos = Usuario.query.filter_by(is_active=True).all()
    total_categorias = Categoria.query.count()
    
    # Ventas del mes actual
    from datetime import datetime
    mes_actual = datetime.now().month
    ventas_mes_actual = Venta.query.filter(
        extract('month', Venta.fecha) == mes_actual
    ).count()
    
    # Productos con stock bajo (menos de 10 unidades)
    productos_bajo_stock = Producto.query.filter(Producto.stock < 10).count()
    
    # Ticket promedio
    total_ventas_count = Venta.query.count()
    ticket_promedio = total_ventas / total_ventas_count if total_ventas_count > 0 else 0

    # Datos para gráfico
    ventas_por_mes = (
        db.session.query(
            extract('month', Venta.fecha).label('mes'),
            func.sum(Venta.total).label('total_mes')
        )
        .group_by('mes')
        .order_by('mes')
        .all()
    )

    meses = []
    montos = []
    nombres_meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

    for mes, total in ventas_por_mes:
        meses.append(nombres_meses[int(mes) - 1])
        montos.append(round(total, 2))

    return render_template(
        'admin/dashboard.html',
        total_usuarios=total_usuarios,
        total_productos=total_productos,
        total_ventas=total_ventas,
        productos_destacados=productos_destacados,
        usuarios_activos=usuarios_activos,
        total_categorias=total_categorias,
        ventas_mes_actual=ventas_mes_actual,
        productos_bajo_stock=productos_bajo_stock,
        ticket_promedio=ticket_promedio,
        meses=meses,
        montos=montos,
        now=datetime.now()
    )
@admin_cp.route('/uploads/productos/<filename>')
def admin_serve_uploaded_file(filename):
    # Ruta absoluta a la carpeta de uploads
    uploads_dir = os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads', 'productos')
    return send_from_directory(uploads_dir, filename)
# -------------------------------
# Gestion de Usuarios
# -------------------------------
@admin_cp.route('/gestion_usuarios')
@login_required
def gestion_usuarios():
    if not current_user.is_admin:
        return redirect(url_for('inicio_cp.inicio_publico'))

    usuarios = Usuario.query.order_by(Usuario.created_at.desc()).all()
    
    # Estadísticas para mostrar
    total_usuarios = Usuario.query.count()
    total_admins = Usuario.query.filter_by(is_admin=True).count()
    usuarios_activos = Usuario.query.filter_by(is_active=True).count()
    
    # Usuarios nuevos este mes
    from datetime import datetime
    mes_actual = datetime.now().month
    nuevos_este_mes = Usuario.query.filter(
        extract('month', Usuario.created_at) == mes_actual
    ).count()

    return render_template('admin/users/usuarios.html', 
                         usuarios=usuarios,
                         total_usuarios=total_usuarios,
                         total_admins=total_admins,
                         usuarios_activos=usuarios_activos,
                         nuevos_este_mes=nuevos_este_mes)

@admin_cp.route('/usuarios/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_usuario():
    """Crear un nuevo usuario."""
    if not current_user.is_admin:
        return redirect(url_for('inicio_cp.inicio_publico'))

    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        is_admin = 'is_admin' in request.form

        if Usuario.query.filter_by(email=email).first():
            flash('El correo ya está registrado.', 'danger')
            return redirect(url_for('admin.nuevo_usuario'))

        nuevo = Usuario(
            username=username,
            email=email,
            is_admin=is_admin,
            password_hash=generate_password_hash(password)
        )
        db.session.add(nuevo)
        db.session.commit()
        flash('Usuario creado exitosamente.', 'success')
        return redirect(url_for('admin.gestion_usuarios'))

    return render_template('admin/users/nuevo_usuario.html')


@admin_cp.route('/usuarios/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_usuario(id):
    """Editar un usuario existente."""
    if not current_user.is_admin:
        return redirect(url_for('inicio_cp.inicio_publico'))

    usuario = Usuario.query.get_or_404(id)

    if request.method == 'POST':
        usuario.username = request.form['username']
        usuario.email = request.form['email']
        usuario.is_admin = 'is_admin' in request.form

        # Si se envió una nueva contraseña
        if request.form.get('password'):
            usuario.password_hash = generate_password_hash(request.form['password'])

        db.session.commit()
        flash('Usuario actualizado correctamente.', 'success')
        return redirect(url_for('admin.gestion_usuarios'))

    return render_template('admin/users/editar_usuario.html', usuario=usuario)


@admin_cp.route('/usuarios/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar_usuario(id):
    """Eliminar un usuario."""
    if not current_user.is_admin:
        return redirect(url_for('inicio_cp.inicio_publico'))

    usuario = Usuario.query.get_or_404(id)
    db.session.delete(usuario)
    db.session.commit()
    flash('Usuario eliminado correctamente.', 'success')
    return redirect(url_for('admin.gestion_usuarios'))


# =====================================================
#  GESTIÓN DE PRODUCTOS
# =====================================================
@admin_cp.route('/admin/gestion_productos')
def gestion_productos():
    productos = Producto.query.order_by(Producto.id.desc()).all()
    categorias = Categoria.query.order_by(Categoria.nombre.asc()).all()
    
    # Estadísticas para mostrar
    total_productos = Producto.query.count()
    productos_destacados = Producto.query.filter_by(destacado=True).count()
    stock_bajo = Producto.query.filter(Producto.stock < 3).count()
    total_categorias = Categoria.query.count()
    
    return render_template('admin/productos/productos.html', 
                         productos=productos, 
                         categorias=categorias,
                         total_productos=total_productos,
                         productos_destacados=productos_destacados,
                         stock_bajo=stock_bajo,
                         total_categorias=total_categorias)

# =====================================================
#  NUEVO PRODUCTO
# =====================================================
UPLOAD_FOLDER = 'app/static/uploads/productos'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@admin_cp.route('/admin/nuevo_producto', methods=['GET', 'POST'])
def nuevo_producto():
    categorias = Categoria.query.all()

    if request.method == 'POST':
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        precio = float(request.form['precio'])
        stock = int(request.form['stock'])
        categoria_id = request.form.get('categoria_id') or None
        destacado = 'destacado' in request.form

        imagen_archivo = request.files.get('imagen')
        nombre_imagen = None

        # 🔹 Subida de imagen
        if imagen_archivo and allowed_file(imagen_archivo.filename):
            filename = secure_filename(imagen_archivo.filename)
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            path = os.path.join(UPLOAD_FOLDER, filename)
            imagen_archivo.save(path)
            nombre_imagen = filename

        nuevo = Producto(
            nombre=nombre,
            descripcion=descripcion,
            precio=precio,
            stock=stock,
            categoria_id=categoria_id,
            destacado=destacado,
            imagen=nombre_imagen
        )

        db.session.add(nuevo)
        db.session.commit()
        flash('✅ Producto creado correctamente.', 'success')

        return redirect(url_for('admin.gestion_productos'))

    return render_template('admin/productos/nuevo_producto.html', categorias=categorias)
# =====================================================
#  EDITAR PRODUCTO
# =====================================================
@admin_cp.route('/admin/editar_producto/<int:id>', methods=['GET', 'POST'])
def editar_producto(id):
    producto = Producto.query.get_or_404(id)
    categorias = Categoria.query.all()

    if request.method == 'POST':
        producto.nombre = request.form['nombre']
        producto.descripcion = request.form['descripcion']
        producto.precio = float(request.form['precio'])
        producto.stock = int(request.form['stock'])
        producto.categoria_id = request.form.get('categoria_id') or None
        producto.destacado = 'destacado' in request.form

        imagen_archivo = request.files.get('imagen')

        # 🔹 Si se sube una nueva imagen, reemplazamos la anterior
        if imagen_archivo and allowed_file(imagen_archivo.filename):
            filename = secure_filename(imagen_archivo.filename)
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            path = os.path.join(UPLOAD_FOLDER, filename)
            imagen_archivo.save(path)

            # Eliminar imagen anterior si existía
            if producto.imagen:
                old_path = os.path.join(UPLOAD_FOLDER, producto.imagen)
                if os.path.exists(old_path):
                    os.remove(old_path)

            producto.imagen = filename

        db.session.commit()
        flash('✅ Producto actualizado correctamente.', 'success')
        return redirect(url_for('admin.gestion_productos'))

    return render_template('admin/productos/editar_producto.html', producto=producto, categorias=categorias)
# =====================================================
#  ELIMINAR PRODUCTO
# =====================================================
@admin_cp.route('/admin/eliminar_producto/<int:id>', methods=['POST'])
def eliminar_producto(id):
    producto = Producto.query.get_or_404(id)
    db.session.delete(producto)
    db.session.commit()
    flash('🗑️ Producto eliminado correctamente', 'danger')
    return redirect(url_for('admin.gestion_productos'))

# =====================================================
#  CRUD DE CATEGORÍAS
# =====================================================


@admin_cp.route('/admin/nueva_categoria', methods=['POST'])
def nueva_categoria():
    nombre = request.form['nombre']
    descripcion = request.form.get('descripcion', '')

    if Categoria.query.filter_by(nombre=nombre).first():
        flash('⚠️ La categoría ya existe', 'warning')
    else:
        categoria = Categoria(nombre=nombre, descripcion=descripcion)
        db.session.add(categoria)
        db.session.commit()
        flash('✅ Categoría creada correctamente', 'success')

    return redirect(url_for('admin.gestion_productos'))

@admin_cp.route('/admin/eliminar_categoria/<int:id>', methods=['POST'])
def eliminar_categoria(id):
    categoria = Categoria.query.get_or_404(id)
    db.session.delete(categoria)
    db.session.commit()
    flash('🗑️ Categoría eliminada', 'danger')
    return redirect(url_for('admin.gestion_productos'))

@admin_cp.route('/admin/editar_categoria/<int:id>', methods=['POST'])
def editar_categoria(id):
    categoria = Categoria.query.get_or_404(id)
    categoria.nombre = request.form['nombre']
    categoria.descripcion = request.form.get('descripcion', '')
    db.session.commit()
    flash('✏️ Categoría actualizada', 'info')
    return redirect(url_for('admin.gestion_productos'))
# =====================================================
#  GESTIÓN DE VENTAS
# =====================================================

# LISTAR VENTAS
@admin_cp.route('/admin/gestion_ventas')
def gestion_ventas():
    # --- FILTROS recibidos desde la UI ---
    fecha_desde = request.args.get('fecha_desde')
    fecha_hasta = request.args.get('fecha_hasta')
    cliente = request.args.get('cliente', '').strip()

    ventas_query = Venta.query
    gastos_query = Gasto.query

    # Si no hay filtros, filtramos por el día actual (inicio -> fin del día)
    if not fecha_desde and not fecha_hasta and not cliente:
        hoy = date.today()
        inicio = datetime.combine(hoy, time.min)   # 00:00:00
        fin = datetime.combine(hoy, time.max)      # 23:59:59.999999
        ventas_query = ventas_query.filter(Venta.fecha >= inicio, Venta.fecha <= fin)
        gastos_query = gastos_query.filter(Gasto.fecha >= inicio, Gasto.fecha <= fin)
    else:
        # Si se proporcionó fecha_desde
        if fecha_desde:
            try:
                fd = datetime.strptime(fecha_desde, "%Y-%m-%d").date()
                inicio = datetime.combine(fd, time.min)
                ventas_query = ventas_query.filter(Venta.fecha >= inicio)
                gastos_query = gastos_query.filter(Gasto.fecha >= inicio)
            except ValueError:
                # fecha inválida -> ignoramos el filtro (o podrías flash de aviso)
                pass

        # Si se proporcionó fecha_hasta
        if fecha_hasta:
            try:
                fh = datetime.strptime(fecha_hasta, "%Y-%m-%d").date()
                fin = datetime.combine(fh, time.max)
                ventas_query = ventas_query.filter(Venta.fecha <= fin)
                gastos_query = gastos_query.filter(Gasto.fecha <= fin)
            except ValueError:
                pass

        # Filtro por cliente (aplica solo para ventas)
        if cliente:
            ventas_query = ventas_query.join(Usuario).filter(Usuario.username.ilike(f"%{cliente}%"))

    # Ejecutar consultas y ordenar por fecha descendente
    ventas = ventas_query.order_by(Venta.fecha.desc()).all()
    gastos = gastos_query.order_by(Gasto.fecha.desc()).all()

    # --- Cálculos de totales ---
    total_ventas = sum(v.total for v in ventas) if ventas else 0.0
    total_gastos = sum(g.monto for g in gastos) if gastos else 0.0
    total_neto = total_ventas - total_gastos

    # Pasar también los valores de filtro a la plantilla para mantener el formulario
    return render_template(
        'admin/ventas/gestion_ventas.html',
        ventas=ventas,
        gastos=gastos,
        total_ventas=total_ventas,
        total_gastos=total_gastos,
        total_neto=total_neto,
        filtro_fecha_desde=fecha_desde or '',
        filtro_fecha_hasta=fecha_hasta or '',
        filtro_cliente=cliente or ''
    )


# NUEVA VENTA
@admin_cp.route('/admin/nueva_venta', methods=['GET', 'POST'])
def nueva_venta():
    usuarios = Usuario.query.all()
    productos = Producto.query.filter(Producto.stock > 0).all()

    if request.method == 'POST':
        usuario_id = request.form['usuario_id']
        items = request.form.getlist('producto_id')
        cantidades = request.form.getlist('cantidad')

        if not items:
            flash('⚠️ Debes seleccionar al menos un producto.', 'warning')
            return redirect(url_for('admin.nueva_venta'))

        venta = Venta(usuario_id=usuario_id, total=0)
        db.session.add(venta)
        db.session.flush()  # Para obtener ID antes del commit

        total = 0
        for i, prod_id in enumerate(items):
            producto = Producto.query.get(int(prod_id))
            cantidad = int(cantidades[i])
            subtotal = producto.precio * cantidad

            # Descuenta stock
            producto.stock -= cantidad

            detalle = DetalleVenta(
                venta_id=venta.id,
                producto_id=producto.id,
                cantidad=cantidad,
                precio_unitario=producto.precio,
                subtotal=subtotal
            )
            db.session.add(detalle)
            total += subtotal

        venta.total = total
        db.session.commit()

        flash('✅ Venta registrada correctamente', 'success')
        return redirect(url_for('admin.gestion_ventas'))

    return render_template('admin/ventas/nueva_venta.html', usuarios=usuarios, productos=productos)


# DETALLE DE VENTA
@admin_cp.route('/admin/ver_venta/<int:id>')
def ver_venta(id):
    venta = Venta.query.get_or_404(id)
    return render_template('admin/ventas/ver_venta.html', venta=venta)


# ELIMINAR VENTA
@admin_cp.route('/admin/eliminar_venta/<int:id>', methods=['POST'])
def eliminar_venta(id):
    venta = Venta.query.get_or_404(id)
    db.session.delete(venta)
    db.session.commit()
    flash('🗑️ Venta eliminada correctamente', 'danger')
    return redirect(url_for('admin.gestion_ventas'))


# =====================================================
#  CRUD DE GASTOS
# =====================================================
@admin_cp.route('/admin/nuevo_gasto', methods=['POST'])
def nuevo_gasto():
    descripcion = request.form['descripcion']
    monto = float(request.form['monto'])
    categoria = request.form.get('categoria', '')

    nuevo = Gasto(descripcion=descripcion, monto=monto, categoria=categoria)
    db.session.add(nuevo)
    db.session.commit()
    flash('✅ Gasto registrado correctamente.', 'success')

    return redirect(url_for('admin.gestion_ventas'))


@admin_cp.route('/admin/eliminar_gasto/<int:id>', methods=['POST'])
def eliminar_gasto(id):
    gasto = Gasto.query.get_or_404(id)
    db.session.delete(gasto)
    db.session.commit()
    flash('🗑️ Gasto eliminado correctamente.', 'danger')

    return redirect(url_for('admin.gestion_ventas'))


# =====================================================
#  EXPORTAR PDF - REPORTE FINANCIERO
# =====================================================

@admin_cp.route('/admin/exportar_pdf')
def exportar_pdf():
    fecha_desde = request.args.get('fecha_desde')
    fecha_hasta = request.args.get('fecha_hasta')
    cliente = request.args.get('cliente', '').strip()

    ventas_query = Venta.query
    gastos_query = Gasto.query

    # --- Filtros (idénticos a la vista) ---
    if not fecha_desde and not fecha_hasta and not cliente:
        hoy = date.today()
        inicio = datetime.combine(hoy, time.min)
        fin = datetime.combine(hoy, time.max)
        ventas_query = ventas_query.filter(Venta.fecha >= inicio, Venta.fecha <= fin)
        gastos_query = gastos_query.filter(Gasto.fecha >= inicio, Gasto.fecha <= fin)
    else:
        if fecha_desde:
            fd = datetime.strptime(fecha_desde, "%Y-%m-%d").date()
            inicio = datetime.combine(fd, time.min)
            ventas_query = ventas_query.filter(Venta.fecha >= inicio)
            gastos_query = gastos_query.filter(Gasto.fecha >= inicio)
        if fecha_hasta:
            fh = datetime.strptime(fecha_hasta, "%Y-%m-%d").date()
            fin = datetime.combine(fh, time.max)
            ventas_query = ventas_query.filter(Venta.fecha <= fin)
            gastos_query = gastos_query.filter(Gasto.fecha <= fin)
        if cliente:
            ventas_query = ventas_query.join(Usuario).filter(Usuario.username.ilike(f"%{cliente}%"))

    ventas = ventas_query.order_by(Venta.fecha.desc()).all()
    gastos = gastos_query.order_by(Gasto.fecha.desc()).all()

    total_ventas = sum(v.total for v in ventas)
    total_gastos = sum(g.monto for g in gastos)
    total_neto = total_ventas - total_gastos

    # --- Crear el PDF profesional ---
    pdf = FPDF()
    pdf.add_page()

    # Encabezado con logo (si existe)
    logo_path = os.path.join("static", "img", "logo.png")  # ajusta si tu logo está en otro lugar
    if os.path.exists(logo_path):
        pdf.image(logo_path, 10, 8, 25)
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 10, "RopaStore", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, "Reporte Financiero", ln=True, align="C")
    pdf.ln(10)

    # Fecha y filtros
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 8, f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True)
    if fecha_desde or fecha_hasta or cliente:
        pdf.cell(0, 8, "Filtros aplicados:", ln=True)
        if fecha_desde:
            pdf.cell(0, 8, f"  Desde: {fecha_desde}", ln=True)
        if fecha_hasta:
            pdf.cell(0, 8, f"  Hasta: {fecha_hasta}", ln=True)
        if cliente:
            pdf.cell(0, 8, f"  Cliente: {cliente}", ln=True)
    pdf.ln(10)

    # --- Tabla de Totales ---
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(60, 10, "Ventas Totales", 1, 0, "C", True)
    pdf.cell(60, 10, "Gastos Totales", 1, 0, "C", True)
    pdf.cell(60, 10, "Efectivo Neto", 1, 1, "C", True)
    pdf.set_font("Arial", "", 12)
    pdf.set_fill_color(245, 245, 245)
    pdf.cell(60, 10, f"${total_ventas:.2f}", 1, 0, "C", True)
    pdf.cell(60, 10, f"${total_gastos:.2f}", 1, 0, "C", True)
    color = (204, 255, 204) if total_neto >= 0 else (255, 204, 204)
    pdf.set_fill_color(*color)
    pdf.cell(60, 10, f"${total_neto:.2f}", 1, 1, "C", True)
    pdf.ln(10)

    # --- Detalle de Ventas ---
    pdf.set_font("Arial", "B", 13)
    pdf.cell(0, 8, "Detalle de Ventas", ln=True)
    pdf.set_font("Arial", "", 11)
    if ventas:
        for v in ventas:
            cliente_nombre = v.usuario.username if v.usuario else "Cliente desconocido"
            pdf.cell(0, 8, f"#{v.id} - {cliente_nombre} - {v.fecha.strftime('%d/%m/%Y')} - ${v.total:.2f}", ln=True)
    else:
        pdf.cell(0, 8, "Sin registros de ventas.", ln=True)
    pdf.ln(8)

    # --- Detalle de Gastos ---
    pdf.set_font("Arial", "B", 13)
    pdf.cell(0, 8, "Detalle de Gastos", ln=True)
    pdf.set_font("Arial", "", 11)
    if gastos:
        for g in gastos:
            categoria = g.categoria if g.categoria else "Sin categoría"
            pdf.cell(0, 8, f"#{g.id} - {g.descripcion} ({categoria}) - {g.fecha.strftime('%d/%m/%Y')} - ${g.monto:.2f}", ln=True)
    else:
        pdf.cell(0, 8, "Sin registros de gastos.", ln=True)
    pdf.ln(12)

    # --- Firma / Pie ---
    pdf.set_font("Arial", "I", 10)
    pdf.cell(0, 8, "RopaStore - Sistema de Gestión Financiera", ln=True, align="C")

    # --- Exportar correctamente en memoria ---
    pdf_content = pdf.output(dest="S").encode("latin1")
    buffer = BytesIO(pdf_content)
    buffer.seek(0)
    filename = f"reporte_financiero_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"

    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")


# -------------------------------
# USUARIO DASHBOARD
# -------------------------------
@usuario_cp.route('/dashboard')
@login_required
def user_dashboard():
    categorias = Categoria.query.all()
    texto = request.args.get('buscar', '').strip()
    categoria_id = request.args.get('categoria')

    query = Producto.query
    if texto:
        query = query.filter(Producto.nombre.ilike(f"%{texto}%"))
    if categoria_id:
        query = query.filter(Producto.categoria_id == categoria_id)

    productos = query.order_by(Producto.created_at.desc()).all()
    return render_template(
        'users/dashboard.html',
        categorias=categorias,
        productos=productos
    )

# -------------------------------
# VER CARRITO
# -------------------------------
@usuario_cp.route('/carrito')
@login_required
def ver_carrito():
    carrito = session.get('carrito', {})
    total = sum(item['precio'] * item['cantidad'] for item in carrito.values())
    return render_template('users/carrito.html', carrito=carrito, total=total)

# -------------------------------
# AGREGAR AL CARRITO
# -------------------------------
@usuario_cp.route('/agregar_carrito/<int:producto_id>', methods=['POST'])
@login_required
def agregar_carrito(producto_id):
    producto = Producto.query.get_or_404(producto_id)
    carrito = session.get('carrito', {})

    if str(producto_id) in carrito:
        carrito[str(producto_id)]['cantidad'] += 1
    else:
        carrito[str(producto_id)] = {
            'id': producto.id,
            'nombre': producto.nombre,
            'precio': producto.precio,
            'imagen': producto.imagen,
            'cantidad': 1
        }

    session['carrito'] = carrito
    session.modified = True
    flash(f"{producto.nombre} agregado al carrito.", "success")
    return redirect(url_for('usuario_cp.user_dashboard'))

# -------------------------------
# ELIMINAR DEL CARRITO
# -------------------------------
@usuario_cp.route('/eliminar_carrito/<int:producto_id>')
@login_required
def eliminar_carrito(producto_id):
    carrito = session.get('carrito', {})
    carrito.pop(str(producto_id), None)
    session['carrito'] = carrito
    session.modified = True
    flash("Producto eliminado del carrito.", "warning")
    return redirect(url_for('usuario_cp.ver_carrito'))

# -------------------------------
# VACIAR CARRITO
# -------------------------------
@usuario_cp.route('/vaciar_carrito')
@login_required
def vaciar_carrito():
    session.pop('carrito', None)
    flash("Carrito vaciado.", "info")
    return redirect(url_for('usuario_cp.ver_carrito'))
# -------------------------------
# RUTA DE INVENTARIO (ADMIN)
# -------------------------------
@admin_cp.route('/inventario')
@login_required
def inventario():
   
    
    # Obtener todos los productos con sus categorías
    productos = Producto.query.options(db.joinedload(Producto.categoria)).all()
    
    return render_template('admin/inventario/inventario.html', productos=productos)


# -------------------------------
# EDITAR PRODUCTO-inventario
# -------------------------------
@admin_cp.route('/admin/editar_productos/<int:id>', methods=['GET', 'POST'])
def editar_productos(id):
    producto = Producto.query.get_or_404(id)
    categorias = Categoria.query.all()

    if request.method == 'POST':
        producto.nombre = request.form['nombre']
        producto.descripcion = request.form['descripcion']
        producto.precio = float(request.form['precio'])
        producto.stock = int(request.form['stock'])
        producto.categoria_id = request.form.get('categoria_id') or None
        producto.destacado = 'destacado' in request.form

        imagen_archivo = request.files.get('imagen')

        # 🔹 Si se sube una nueva imagen, reemplazamos la anterior
        if imagen_archivo and allowed_file(imagen_archivo.filename):
            filename = secure_filename(imagen_archivo.filename)
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            path = os.path.join(UPLOAD_FOLDER, filename)
            imagen_archivo.save(path)

            # Eliminar imagen anterior si existía
            if producto.imagen:
                old_path = os.path.join(UPLOAD_FOLDER, producto.imagen)
                if os.path.exists(old_path):
                    os.remove(old_path)

            producto.imagen = filename

        db.session.commit()
        flash('✅ Producto actualizado correctamente.', 'success')
        return redirect(url_for('admin.inventario'))

    return render_template('admin/inventario/editar_productos.html', producto=producto, categorias=categorias) 
@admin_cp.route('/admin/nuevos_productos', methods=['GET', 'POST'])
def nuevos_productos():
    categorias = Categoria.query.all()

    if request.method == 'POST':
        nombre = request.form['nombre']
        descripcion = request.form['descripcion']
        precio = float(request.form['precio'])
        stock = int(request.form['stock'])
        categoria_id = request.form.get('categoria_id') or None
        destacado = 'destacado' in request.form

        imagen_archivo = request.files.get('imagen')
        nombre_imagen = None

        # 🔹 Subida de imagen
        if imagen_archivo and allowed_file(imagen_archivo.filename):
            filename = secure_filename(imagen_archivo.filename)
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            path = os.path.join(UPLOAD_FOLDER, filename)
            imagen_archivo.save(path)
            nombre_imagen = filename

        nuevo = Producto(
            nombre=nombre,
            descripcion=descripcion,
            precio=precio,
            stock=stock,
            categoria_id=categoria_id,
            destacado=destacado,
            imagen=nombre_imagen
        )

        db.session.add(nuevo)
        db.session.commit()
        flash('✅ Producto creado correctamente.', 'success')

        return redirect(url_for('admin.inventario'))

    return render_template('admin/inventario/nuevo_producto.html', categorias=categorias)



