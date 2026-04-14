document.addEventListener('DOMContentLoaded', () => {
    // --- ESTADO GLOBAL ---
    let hoyReal = new Date();
    let mesActual = hoyReal.getMonth();
    let añoActual = hoyReal.getFullYear();
    let fechaSeleccionada = "";
    let indiceEdicion = -1;
    let chartInstance = null;
    let clientesAgrupados = []; 

    let configBanner = JSON.parse(localStorage.getItem('pelu_config_v2')) || {
        titulo: "Beauty Palace",
        fondo: "https://images.unsplash.com/photo-1560066984-138dadb4c035?q=80",
        logo: ""
    };
    
    let tempImageBase64 = configBanner.fondo; 
    let tempLogoBase64 = configBanner.logo; 
    let registros = JSON.parse(localStorage.getItem('pelu_datos_v6')) || [];
    
    const contenedor = document.getElementById('calendar');
    const displayMes = document.getElementById('monthYear');

    // --- 1. MICRO-INTERACCIONES (Efecto Ripple) ---
    function createRipple(event) {
        const button = event.currentTarget;
        const circle = document.createElement("span");
        const diameter = Math.max(button.clientWidth, button.clientHeight);
        const radius = diameter / 2;

        circle.style.width = circle.style.height = `${diameter}px`;
        circle.style.left = `${event.clientX - button.offsetLeft - radius}px`;
        circle.style.top = `${event.clientY - button.offsetTop - radius}px`;
        circle.classList.add("m3-ripple");

        const ripple = button.getElementsByClassName("m3-ripple")[0];
        if (ripple) ripple.remove();
        button.appendChild(circle);
    }

    document.querySelectorAll('.m3-btn-filled, .m3-btn-text, .m3-btn-fab-extended, .rail-item, .m3-nav-item, .m3-card-interactive').forEach(btn => {
        btn.addEventListener('click', createRipple);
    });

    // --- 2. CONFIGURACIÓN VISUAL Y GREETING ---
    function aplicarConfigVisual() {
        document.getElementById('txtBannerDisplay').innerText = configBanner.titulo;
        document.getElementById('bannerBg').style.backgroundImage = `url('${configBanner.fondo}')`;
        document.getElementById('cfgTitulo').value = configBanner.titulo;
        
        const perfilDisplay = document.getElementById('perfilDisplay');
        if (configBanner.logo) {
            perfilDisplay.innerHTML = `<img src="${configBanner.logo}" alt="Perfil">`;
        }
    }

    function actualizarBannerInfo() {
        const ahora = new Date();
        const hora = ahora.getHours();
        let saludo = "¡Buenas noches!";
        if (hora >= 5 && hora < 12) saludo = "¡Buenos días!";
        else if (hora >= 12 && hora < 19) saludo = "¡Buenas tardes!";
        
        document.getElementById('saludoText').innerText = saludo;

        const strHoy = `${hoyReal.getFullYear()}-${String(hoyReal.getMonth() + 1).padStart(2, '0')}-${String(hoyReal.getDate()).padStart(2, '0')}`;
        const turnosHoy = registros.filter(r => r.fecha === strHoy && r.tipo === 'ingreso').length;
        
        document.getElementById('contadorTurnos').innerHTML = `
            <span class="material-symbols-rounded">notifications</span>
            <span>${turnosHoy} Turnos hoy</span>
        `;
    }

    // Lectores de archivos (M3)
    const inputFondo = document.getElementById('cfgFondoFile');
    if(inputFondo) inputFondo.addEventListener('change', function(e) {
        if (this.files[0]) {
            const reader = new FileReader();
            reader.onload = (evento) => tempImageBase64 = evento.target.result;
            reader.readAsDataURL(this.files[0]);
        }
    });

    const inputLogo = document.getElementById('cfgLogoFile');
    if(inputLogo) inputLogo.addEventListener('change', function(e) {
        if (this.files[0]) {
            const reader = new FileReader();
            reader.onload = (evento) => tempLogoBase64 = evento.target.result;
            reader.readAsDataURL(this.files[0]);
        }
    });

    // --- 3. RENDERIZADO DEL CALENDARIO ---
    window.renderizar = () => {
        const skeleton = document.getElementById('calendar-skeleton');
        const calCard = document.querySelector('.m3-calendar-card');
        
        if(skeleton) skeleton.style.display = 'grid';
        if(calCard) calCard.style.opacity = '0.3';

        setTimeout(() => {
            if(skeleton) skeleton.style.display = 'none';
            if(calCard) calCard.style.opacity = '1';
            
            contenedor.innerHTML = '';
            const meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
            displayMes.innerText = `${meses[mesActual]} ${añoActual}`;

            const primerDia = new Date(añoActual, mesActual, 1).getDay();
            const totalDias = new Date(añoActual, mesActual + 1, 0).getDate();
            
            for (let i = 0; i < primerDia; i++) {
                contenedor.appendChild(Object.assign(document.createElement('div'), {className: 'day empty'}));
            }

            for (let dia = 1; dia <= totalDias; dia++) {
                const fKey = `${añoActual}-${String(mesActual + 1).padStart(2, '0')}-${String(dia).padStart(2, '0')}`;
                const regDia = registros.filter(r => r.fecha === fKey);
                
                const diaDiv = document.createElement('div');
                diaDiv.className = 'day';
                if(dia === hoyReal.getDate() && mesActual === hoyReal.getMonth() && añoActual === hoyReal.getFullYear()) {
                    diaDiv.classList.add('today');
                }

                diaDiv.innerHTML = `<span class="day-number">${dia}</span>`;
                const list = document.createElement('div');
                list.className = 'day-events'; 
                
                regDia.sort((a,b) => (a.hora > b.hora ? 1 : -1)).forEach(r => {
                    const dot = document.createElement('div');
                    dot.className = `event-indicator ${r.tipo === 'gasto' ? 'event-gasto' : 'event-ingreso'}`;
                    list.appendChild(dot);
                });

                diaDiv.appendChild(list);
                diaDiv.onclick = () => window.abrirModalDia(fKey);
                contenedor.appendChild(diaDiv);
            }
            actualizarEconomia();
            renderizarListaClientes(); 
        }, 400); 
    };

    // --- 4. SWIPE Y MESES ---
    contenedor.addEventListener('touchstart', e => { 
        touchStartX = e.changedTouches[0].screenX; 
        touchStartY = e.changedTouches[0].screenY;
    }, {passive: true});

    contenedor.addEventListener('touchend', e => {
        touchEndX = e.changedTouches[0].screenX;
        let diffX = Math.abs(touchEndX - touchStartX);
        let diffY = Math.abs(e.changedTouches[0].screenY - touchStartY);

        if (diffX > diffY && diffX > 50) {
            if (touchEndX < touchStartX) cambiarMes(1);
            if (touchEndX > touchStartX) cambiarMes(-1);
        }
    }, {passive: true});

    function cambiarMes(delta) {
        mesActual += delta;
        if (mesActual > 11) { mesActual = 0; añoActual++; }
        if (mesActual < 0) { mesActual = 11; añoActual--; }
        renderizar();
    }
    document.getElementById('prevMonth').onclick = () => cambiarMes(-1);
    document.getElementById('nextMonth').onclick = () => cambiarMes(1);

    // --- 5. CONTROL DE VISTAS (SPA M3) ---
    window.cambiarVista = (vistaId) => {
        document.querySelectorAll('.vista').forEach(v => {
            v.classList.remove('activa');
            v.classList.add('oculta');
        });
        document.getElementById(`vista-${vistaId}`).classList.remove('oculta');
        document.getElementById(`vista-${vistaId}`).classList.add('activa');

        document.querySelectorAll('.rail-item, .m3-nav-item').forEach(nav => {
            if (nav.getAttribute('onclick').includes(vistaId)) {
                nav.classList.add('active');
            } else {
                nav.classList.remove('active');
            }
        });

        if (vistaId === 'hoy') renderizarVistaHoy();
        else if (vistaId === 'reportes') window.filtrarGrafico('mensual');
        else if (vistaId === 'calendario') window.renderizar();
        else if (vistaId === 'clientes') renderizarListaClientes();
    };

    // --- 6. LÓGICA DEL CRM (CLIENTES) ---
    function procesarDatosCRM() {
        const ingresos = registros.filter(r => r.tipo === 'ingreso');
        const mapaClientes = new Map();

        ingresos.forEach(turno => {
            let nombreCliente = turno.titulo.split('-')[0].trim();
            let servicio = turno.titulo.split('-')[1]?.trim() || 'Servicio General';
            let clave = turno.telefono ? turno.telefono.replace(/\D/g, '') : nombreCliente.toLowerCase();
            
            if(!clave) return;

            if (!mapaClientes.has(clave)) {
                mapaClientes.set(clave, {
                    nombre: nombreCliente,
                    telefono: turno.telefono || '',
                    totalGastado: 0,
                    turnos: []
                });
            }

            let cliente = mapaClientes.get(clave);
            cliente.totalGastado += Number(turno.monto);
            let turnoConServicio = {...turno, servicioReal: servicio};
            cliente.turnos.push(turnoConServicio);
        });

        clientesAgrupados = Array.from(mapaClientes.values()).map(c => {
            c.turnos.sort((a, b) => new Date(b.fecha) - new Date(a.fecha));
            c.ultimaVisita = c.turnos[0].fecha;
            return c;
        });
        
        clientesAgrupados.sort((a, b) => new Date(b.ultimaVisita) - new Date(a.ultimaVisita));
    }

    function renderizarListaClientes(terminoBusqueda = "") {
        procesarDatosCRM();
        const lista = document.getElementById('listaClientesActivos');
        if(!lista) return;
        lista.innerHTML = '';

        let filtrados = clientesAgrupados;
        if (terminoBusqueda) {
            const termino = terminoBusqueda.toLowerCase();
            filtrados = clientesAgrupados.filter(c => 
                c.nombre.toLowerCase().includes(termino) || 
                c.telefono.includes(termino)
            );
        }

        if(filtrados.length === 0) {
            lista.innerHTML = `<div style="text-align:center; padding: 48px 16px; color: var(--m3-on-surface-variant);">
                <span class="material-symbols-rounded" style="font-size: 48px; opacity: 0.5; margin-bottom:16px;">search_off</span>
                <p>No se encontraron clientes.</p>
            </div>`;
            return;
        }

        filtrados.forEach((c, index) => {
            const card = document.createElement('div');
            card.className = 'm3-card-list-item'; 
            
            const f = c.ultimaVisita.split('-');
            const fechaFormateada = `${f[2]}/${f[1]}/${f[0]}`;

            let btnWsp = '';
            if (c.telefono) {
                const telLimpio = c.telefono.replace(/\D/g, ''); 
                // Mensaje genérico para escribirle a alguien desde el directorio
                const mensaje = encodeURIComponent(`¡Hola ${c.nombre}! Te escribimos de ${configBanner.titulo}... `);
                
                btnWsp = `<a href="https://wa.me/${telLimpio}?text=${mensaje}" target="_blank" class="m3-icon-btn" style="background:var(--m3-surface-variant);" onclick="event.stopPropagation()"><span class="material-symbols-rounded" style="color:var(--m3-primary); font-size:20px;">chat</span></a>`;
            }

            card.innerHTML = `
                <div class="m3-item-leading">
                    <span class="material-symbols-rounded">person</span>
                </div>
                <div class="m3-item-content">
                    <span class="m3-item-title">${c.nombre}</span>
                    <span class="m3-item-subtitle">Última vez: ${fechaFormateada}</span>
                </div>
                <div style="display:flex; align-items:center; gap:8px;">
                    ${btnWsp}
                    <span class="material-symbols-rounded" style="color:var(--m3-on-surface-variant);">chevron_right</span>
                </div>
            `;
            card.onclick = () => window.abrirModalCliente(index, filtrados);
            lista.appendChild(card);
        });
    }

    window.buscarCliente = () => {
        const termino = document.getElementById('buscadorClientes').value;
        renderizarListaClientes(termino);
    };

    window.abrirModalCliente = (index, arrayBase) => {
        const cliente = arrayBase[index];
        document.getElementById('detalleNombreCliente').innerText = cliente.nombre;
        document.getElementById('detalleTelCliente').innerText = cliente.telefono || "Sin teléfono";
        document.getElementById('detalleTotalInvertido').innerText = `$${cliente.totalGastado.toLocaleString()}`;
        
        const fUltima = cliente.ultimaVisita.split('-');
        document.getElementById('detalleUltimaVisita').innerText = `${fUltima[2]}/${fUltima[1]}/${fUltima[0]}`;

        const listaHistorial = document.getElementById('listaHistorialCliente');
        listaHistorial.innerHTML = '';
        
        cliente.turnos.forEach(t => {
            const f = t.fecha.split('-');
            const fechaItem = `${f[2]}/${f[1]}/${f[0]}`;
            
            const card = document.createElement('div');
            card.className = 'm3-card-list-item';
            card.style.marginBottom = '8px';
            card.innerHTML = `
                <div class="m3-item-content">
                    <span class="m3-item-title">${t.servicioReal}</span>
                    <span class="m3-item-subtitle">${fechaItem} • ${t.hora || '--:--'}</span>
                </div>
                <span class="m3-item-amount text-success">$${t.monto}</span>
            `;
            listaHistorial.appendChild(card);
        });

        document.getElementById('modalCliente').style.display = 'flex';
    };

    window.cerrarModalCliente = () => document.getElementById('modalCliente').style.display = 'none';

    // --- 7. VISTA HOY ---
    function renderizarVistaHoy() {
        const strHoy = `${hoyReal.getFullYear()}-${String(hoyReal.getMonth() + 1).padStart(2, '0')}-${String(hoyReal.getDate()).padStart(2, '0')}`;
        fechaSeleccionada = strHoy; 
        const regHoy = registros.filter(r => r.fecha === strHoy);
        
        document.getElementById('fechaHoyDisplay').innerText = strHoy.split('-').reverse().join('/');
        const lista = document.getElementById('listaTurnosHoyVista');
        
        if(regHoy.length === 0) {
            lista.innerHTML = `<div style="text-align:center; padding: 48px 16px; color: var(--m3-on-surface-variant);">
                <span class="material-symbols-rounded" style="font-size: 48px; opacity: 0.5; margin-bottom:16px;">event_busy</span>
                <p>No hay turnos programados para hoy.</p>
            </div>`;
            return;
        }
        
        lista.innerHTML = '';
        regHoy.sort((a,b) => (a.hora > b.hora ? 1 : -1)).forEach(r => {
            const card = document.createElement('div');
            card.className = 'm3-card-list-item'; 
            
            const icono = r.tipo === 'gasto' ? 'shopping_cart' : 'content_cut';
            const colorMonto = r.tipo === 'gasto' ? 'text-error' : 'text-success';
            
            let btnWsp = '';
            if (r.tipo === 'ingreso' && r.telefono) {
                const telLimpio = r.telefono.replace(/\D/g, ''); 
                // Extraemos solo el nombre (antes del guion) para que el saludo sea natural
                const nombreCorto = r.titulo.split('-')[0].trim();
                const mensaje = encodeURIComponent(`¡Hola ${nombreCorto}! Te escribimos de ${configBanner.titulo} para recordarte tu turno de hoy a las ${r.hora}. ¡Te esperamos!`);
                
                btnWsp = `<a href="https://wa.me/${telLimpio}?text=${mensaje}" target="_blank" class="wsp-btn" onclick="event.stopPropagation()"><span class="material-symbols-rounded" style="color:white; font-size:18px;">chat</span></a>`;
            }

            card.innerHTML = `
                <div class="m3-item-leading">
                    <span class="material-symbols-rounded">${icono}</span>
                </div>
                <div class="m3-item-content">
                    <span class="m3-item-title">${r.titulo}</span>
                    <span class="m3-item-subtitle">${r.hora || '--:--'}</span>
                </div>
                <div style="display:flex; align-items:center; gap:12px;">
                    ${btnWsp}
                    <span class="m3-item-amount ${colorMonto}">$${r.monto}</span>
                </div>
            `;
            card.onclick = () => window.prepararEdicion(registros.indexOf(r));
            lista.appendChild(card);
        });
    }

    // --- 8. LÓGICA DE MODALES DE REGISTRO (CON SERVICIOS) ---
    
    // Toggle para esconder Servicios si es un gasto y cambiar el Título dinámicamente
    window.toggleFormularioTipo = () => {
        const esGasto = document.querySelector('input[name="tipoRegistro"][value="gasto"]').checked;
        const campoServicios = document.getElementById('campoServicios');
        const campoTelefono = document.getElementById('campoTelefono');
        const tituloModal = document.getElementById('modalTitle');
        
        if (esGasto) {
            campoServicios.style.display = 'none';
            campoTelefono.style.display = 'none';
            document.getElementById('selectServicio').value = ""; 
            
            // CORRECCIÓN 1: Título dinámico para Gasto
            tituloModal.innerText = indiceEdicion > -1 ? "Editar Gasto" : "Nuevo Gasto";
        } else {
            campoServicios.style.display = 'block';
            campoTelefono.style.display = 'block';
            
            // CORRECCIÓN 1: Título dinámico para Cita
            tituloModal.innerText = indiceEdicion > -1 ? "Editar Cita" : "Nueva Cita";
        }
    };

    window.actualizarMontoSugerido = () => {
        const servicioSeleccionado = document.getElementById('selectServicio').value;
        const inputNombre = document.getElementById('nombreCliente');
        
        if (servicioSeleccionado !== "") {
            if (inputNombre.value.includes('-')) {
                let soloNombre = inputNombre.value.split('-')[0].trim();
                inputNombre.value = `${soloNombre} - ${servicioSeleccionado}`;
            } else if (inputNombre.value !== "") {
                inputNombre.value = `${inputNombre.value.trim()} - ${servicioSeleccionado}`;
            }
        }
    };

    window.abrirModalDia = (fecha) => {
        fechaSeleccionada = fecha;
        const regDia = registros.filter(r => r.fecha === fecha);
        document.getElementById('fechaDiaTitulo').innerText = fecha.split('-').reverse().join('/');
        const lista = document.getElementById('listaTurnosDia');
        lista.innerHTML = regDia.length ? '' : '<p style="text-align:center; color: var(--m3-on-surface-variant); padding:20px;">Sin registros</p>';
        
        regDia.forEach(r => {
            const item = document.createElement('div');
            item.className = 'm3-card-list-item';
            item.style.marginBottom = '8px';
            item.innerHTML = `<div class="m3-item-content"><span class="m3-item-title">${r.titulo}</span></div><span class="m3-item-amount ${r.tipo === 'gasto' ? 'text-error' : 'text-success'}">$${r.monto}</span>`;
            item.onclick = (e) => { e.stopPropagation(); window.prepararEdicion(registros.indexOf(r)); };
            lista.appendChild(item);
        });
        document.getElementById('modalDia').style.display = 'flex';
    };

    window.abrirFormularioNuevo = (desdeModalDia = false) => {
        if (!desdeModalDia) {
            window.cerrarModalDia();
            fechaSeleccionada = `${hoyReal.getFullYear()}-${String(hoyReal.getMonth() + 1).padStart(2, '0')}-${String(hoyReal.getDate()).padStart(2, '0')}`;
        }
        indiceEdicion = -1;
        document.getElementById('nombreCliente').value = "";
        document.getElementById('telefonoCliente').value = "";
        document.getElementById('montoTurno').value = "";
        document.getElementById('horaTurno').value = "";
        document.getElementById('selectServicio').value = "";
        
        document.querySelector('input[name="tipoRegistro"][value="ingreso"]').checked = true;
        window.toggleFormularioTipo(); 
        
        document.getElementById('btnBorrar').style.display = "none";
        document.getElementById('modalTurno').style.display = 'flex';
    };

    window.prepararEdicion = (idx) => {
        window.cerrarModalDia();
        const r = registros[idx];
        indiceEdicion = idx;
        document.getElementById('nombreCliente').value = r.titulo;
        document.getElementById('telefonoCliente').value = r.telefono || "";
        document.getElementById('horaTurno').value = r.hora || "";
        document.getElementById('montoTurno').value = r.monto;
        document.querySelector(`input[name="tipoRegistro"][value="${r.tipo}"]`).checked = true;
        
        window.toggleFormularioTipo();

        if (r.tipo === 'ingreso' && r.titulo.includes('-')) {
            let srv = r.titulo.split('-')[1].trim();
            let select = document.getElementById('selectServicio');
            let existe = Array.from(select.options).some(opt => opt.value === srv);
            if (existe) select.value = srv;
            else select.value = "";
        } else {
            document.getElementById('selectServicio').value = "";
        }
        
        document.getElementById('btnBorrar').style.display = "block";
        document.getElementById('modalTurno').style.display = 'flex';
    };

    window.cerrarModalDia = () => document.getElementById('modalDia').style.display = 'none';
    window.cerrarModal = () => document.getElementById('modalTurno').style.display = 'none';
    window.cerrarConfig = () => document.getElementById('modalConfig').style.display = 'none';
    window.abrirConfig = () => document.getElementById('modalConfig').style.display = 'flex';

    window.guardarConfig = () => {
        configBanner.titulo = document.getElementById('cfgTitulo').value || configBanner.titulo;
        configBanner.fondo = tempImageBase64; 
        configBanner.logo = tempLogoBase64;
        localStorage.setItem('pelu_config_v2', JSON.stringify(configBanner));
        aplicarConfigVisual();
        window.cerrarConfig();
    };

    document.getElementById('btnGuardar').onclick = () => {
        const titulo = document.getElementById('nombreCliente').value;
        const monto = document.getElementById('montoTurno').value;
        const tipoReg = document.querySelector('input[name="tipoRegistro"]:checked').value;
        if(!titulo || !monto) return alert("Por favor completa el concepto y el monto.");

        const dato = {
            fecha: fechaSeleccionada,
            titulo: titulo,
            telefono: document.getElementById('telefonoCliente').value,
            hora: document.getElementById('horaTurno').value,
            monto: Number(monto),
            tipo: tipoReg
        };

        if(indiceEdicion > -1) registros[indiceEdicion] = dato; 
        else registros.push(dato);
        
        localStorage.setItem('pelu_datos_v6', JSON.stringify(registros));
        window.cerrarModal();
        
        if(!document.getElementById('vista-calendario').classList.contains('oculta')) renderizar(); 
        if(!document.getElementById('vista-hoy').classList.contains('oculta')) renderizarVistaHoy();
        if(!document.getElementById('vista-clientes').classList.contains('oculta')) renderizarListaClientes();
        
        actualizarEconomia();
        actualizarBannerInfo(); // CORRECCIÓN 2: Refresca el contador de turnos de hoy
    };

    document.getElementById('btnBorrar').onclick = () => {
        if(confirm("¿Eliminar definitivamente este registro?")) {
            registros.splice(indiceEdicion, 1);
            localStorage.setItem('pelu_datos_v6', JSON.stringify(registros));
            window.cerrarModal();
            
            if(!document.getElementById('vista-calendario').classList.contains('oculta')) renderizar();
            if(!document.getElementById('vista-hoy').classList.contains('oculta')) renderizarVistaHoy();
            if(!document.getElementById('vista-clientes').classList.contains('oculta')) renderizarListaClientes();
            
            actualizarEconomia();
            actualizarBannerInfo(); // CORRECCIÓN 2: Refresca el contador de turnos de hoy
        }
    };

    // --- 9. FINANZAS Y GRÁFICOS ---
    function actualizarEconomia() {
        const mesStr = `${añoActual}-${String(mesActual+1).padStart(2,'0')}`;
        const regMes = registros.filter(r => r.fecha.startsWith(mesStr));
        const ing = regMes.filter(r => r.tipo === 'ingreso').reduce((a, b) => a + Number(b.monto), 0);
        const gas = regMes.filter(r => r.tipo === 'gasto').reduce((a, b) => a + Number(b.monto), 0);
        
        const totIng = document.getElementById('totalIngresos');
        const totGas = document.getElementById('totalGastos');
        const totNet = document.getElementById('totalNeto');
        
        if(totIng) totIng.innerText = `$${ing.toLocaleString()}`;
        if(totGas) totGas.innerText = `$${gas.toLocaleString()}`;
        if(totNet) totNet.innerText = `$${(ing - gas).toLocaleString()}`;
    }

    // --- 10. LICENCIA ---
    const LLAVE_MAESTRA = "SALON-2026"; 
    function verificarAcceso() {
        const activado = localStorage.getItem('app_activada');
        if (activado !== 'true') document.getElementById('bloqueoLicencia').style.display = 'flex';
    }
    window.validarLicencia = () => {
        const input = document.getElementById('inputLicencia').value.trim().toUpperCase();
        if (input === LLAVE_MAESTRA) {
            localStorage.setItem('app_activada', 'true');
            document.getElementById('bloqueoLicencia').style.display = 'none';
        } else {
            document.getElementById('errorLicencia').style.display = 'block';
        }
    };

    // --- INICIALIZACIÓN ---
    verificarAcceso();
    aplicarConfigVisual();
    actualizarBannerInfo();
    window.renderizar();
});