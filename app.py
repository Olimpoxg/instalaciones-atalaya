import streamlit as st
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from streamlit_drawable_canvas import st_canvas
from supabase import create_client, Client
import io
import base64
from PIL import Image

# Configuración de la página optimizada para móvil
st.set_page_config(
    page_title="Albaranes Atalaya",
    page_icon="☕",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Conexión a Supabase
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase: Client = init_supabase()

st.title("☕ Albaranes de Intervención")
st.caption("Cafés Atalaya / Servicios de Recreativos y Café, S.L.")

menu = st.radio("Acción", ["Nuevo Albarán", "Histórico / Reimprimir"], horizontal=True, label_visibility="collapsed")

if menu == "Nuevo Albarán":
    st.subheader("1. Datos del Local y Cliente")
    nombre_local = st.text_input("Nombre del Local (Bar / Establecimiento)")
    col1, col2 = st.columns(2)
    with col1:
        titular = st.text_input("Titular / Responsable")
        cif = st.text_input("C.I.F. / D.N.I.")
        telefono = st.text_input("Teléfono")
    with col2:
        direccion = st.text_input("Dirección")
        localidad = st.text_input("Localidad", value="Pamplona")
        cp = st.text_input("Código Postal", value="31001")

    st.markdown("---")
    st.subheader("2. Tipo de Intervención")
    tipo_intervencion = st.selectbox(
        "Selecciona la operación principal",
        ["Instalación", "Retirada", "Sustitución"]
    )

    st.markdown("---")
    st.subheader("3. Equipos Afectados")
    
    if 'equipos_temp' not in st.session_state:
        st.session_state.equipos_temp = []

    with st.expander("➕ Añadir una máquina a la lista", expanded=True):
        e_accion = st.selectbox("Acción sobre el equipo", ["Instalado", "Retirado"], key="eq_accion")
        e_tipo = st.selectbox("Tipo de Equipo", ["Cafetera", "Molino", "Granizadora"], key="eq_tipo")
        e_fabricante = st.text_input("Fabricante / Marca", key="eq_fab")
        e_modelo = st.text_input("Modelo", key="eq_mod")
        e_serie = st.text_input("Número de Serie (N/S)", key="eq_serie")
        
        if st.button("Añadir equipo al albarán"):
            if e_serie.strip():
                st.session_state.equipos_temp.append({
                    "accion": e_accion,
                    "tipo": e_tipo,
                    "fabricante": e_fabricante,
                    "modelo": e_modelo,
                    "serie": e_serie
                })
                st.success("¡Equipo añadido a la lista!")
                st.rerun()
            else:
                st.warning("Por favor, introduce el número de serie.")

    if st.session_state.equipos_temp:
        st.write("**Equipos registrados para este albarán:**")
        for idx, eq in enumerate(st.session_state.equipos_temp):
            col_info, col_del = st.columns([4, 1])
            with col_info:
                st.text(f"• [{eq['accion']}] {eq['tipo']} - {eq['fabricante']} {eq['modelo']} (N/S: {eq['serie']})")
            with col_del:
                if st.button("🗑️ Quitar", key=f"del_{idx}"):
                    st.session_state.equipos_temp.pop(idx)
                    st.rerun()

    st.markdown("---")
    st.subheader("4. Observaciones")
    observaciones = st.text_area("Notas adicionales", placeholder="Ej: Máquina revisada, pendiente cambio de filtro...")

    st.markdown("---")
    st.subheader("5. Firmas Digitales (Firma con el dedo)")
    
    col_t, col_c = st.columns(2)
    with col_t:
        st.text("Firma Técnico (Mikel)")
        canvas_tecnico = st_canvas(
            fill_color="rgba(255, 255, 255, 0)",
            stroke_width=2,
            stroke_color="#000000",
            background_color="#FFFFFF",
            height=140,
            width=250,
            drawing_mode="freedraw",
            key="canvas_tec"
        )
    with col_c:
        st.text("Firma Titular / Cliente")
        canvas_cliente = st_canvas(
            fill_color="rgba(255, 255, 255, 0)",
            stroke_width=2,
            stroke_color="#000000",
            background_color="#FFFFFF",
            height=140,
            width=250,
            drawing_mode="freedraw",
            key="canvas_cli"
        )

    st.markdown("---")
    if st.button("💾 Guardar Albarán y Generar PDF", type="primary", use_container_width=True):
        if not nombre_local.strip():
            st.error("El nombre del local es obligatorio.")
        elif not st.session_state.equipos_temp:
            st.error("Debes añadir al menos un equipo a la lista.")
        else:
            # Procesar firmas
            sig_tec_b64 = ""
            if canvas_tecnico.image_data is not None:
                img_tec = Image.fromarray(canvas_tecnico.image_data.astype('uint8'), 'RGBA')
                buffered_tec = io.BytesIO()
                img_tec.save(buffered_tec, format="PNG")
                sig_tec_b64 = base64.b64encode(buffered_tec.getvalue()).decode()

            sig_cli_b64 = ""
            if canvas_cliente.image_data is not None:
                img_cli = Image.fromarray(canvas_cliente.image_data.astype('uint8'), 'RGBA')
                buffered_cli = io.BytesIO()
                img_cli.save(buffered_cli, format="PNG")
                sig_cli_b64 = base64.b64encode(buffered_cli.getvalue()).decode()

            # Guardar cabecera en Supabase
            albaran_data = {
                "tipo_intervencion": tipo_intervencion,
                "nombre_local": nombre_local,
                "cif": cif,
                "direccion": direccion,
                "localidad": localidad,
                "cp": cp,
                "telefono": telefono,
                "titular": titular,
                "observaciones": observaciones,
                "tecnico": "Mikel",
                "firma_tecnico": sig_tec_b64,
                "firma_cliente": sig_cli_b64
            }
            
            res = supabase.table("albaranes_instalaciones").insert(albaran_data).execute()
            
            if res.data:
                albaran_id = res.data[0]["id"]
                
                # Guardar equipos asociados
                for eq in st.session_state.equipos_temp:
                    eq_data = {
                        "albaranes_id": albaran_id,
                        "accion": eq["accion"],
                        "tipo_equipo": eq["tipo"],
                        "fabricante": eq["fabricante"],
                        "modelo": eq["modelo"],
                        "num_serie": eq["serie"]
                    }
                    supabase.table("equipos_instalados").insert(eq_data).execute()
                
                st.success(f"¡Albarán #{albaran_id} guardado con éxito en Supabase!")
                st.session_state.equipos_temp = []
            else:
                st.error("Error al guardar en la base de datos.")

elif menu == "Histórico / Reimprimir":
    st.subheader("📁 Histórico de Intervenciones")
    try:
        response = supabase.table("albaranes_instalaciones").select("*").order("id", desc=True).limit(20).execute()
        albaranes = response.data
        
        if not albaranes:
            st.info("No hay albaranes registrados todavía.")
        else:
            for alb in albaranes:
                with st.expander(f"Albarán #{alb['id']} - {alb['nombre_local']} ({alb['tipo_intervencion']} - {alb['fecha'][:10]})"):
                    st.write(f"**Titular:** {alb['titular']} | **Teléfono:** {alb['telefono']}")
                    st.write(f"**Dirección:** {alb['direccion']}, {alb['localidad']}")
                    
                    eq_res = supabase.table("equipos_instalados").select("*").eq("albaranes_id", alb['id']).execute()
                    equipos = eq_res.data
                    
                    st.write("**Equipos:**")
                    for e in equipos:
                        st.text(f"  • [{e['accion']}] {e['tipo_equipo']} - {e['fabricante']} {e['modelo']} (N/S: {e['num_serie']})")
                    
                    if alb['observaciones']:
                        st.write(f"**Observaciones:** {alb['observaciones']}")
    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}")
