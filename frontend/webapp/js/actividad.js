/*
 * Vista Ver actividad (CC-09 y CC-22): historial de eventos del simulador, del mas
 * reciente al mas antiguo, con los nuevos agregados en vivo arriba de la lista.
 * Datos de /api/actividad (ApiLecturaServlet, CC-21) insertados con textContent.
 */
(function (SC, global) {
    'use strict';
    var doc = global.document;
    var lista = doc.getElementById('actividad-lista');
    if (!SC || !SC.vivo || !lista) { return; }
    var botonMas = doc.getElementById('actividad-mas');
    var vacio = doc.getElementById('actividad-vacio');
    var error = doc.getElementById('actividad-error');
    var estado = doc.getElementById('actividad-estado');
    var antesId = null, ultimoId = 0, conexion = null;

    function fila(e) {
        var li = SC.el('li', 'actividad-item');
        var t = SC.el('time', 'actividad-cuando', SC.vivo.cuando(e));
        t.setAttribute('datetime', e.ocurrido);
        li.appendChild(t);
        var etiqueta = SC.el('span', 'actividad-etiqueta');
        etiqueta.appendChild(SC.vivo.insignia(e));
        li.appendChild(etiqueta);
        li.appendChild(SC.el('span', 'actividad-modulo', SC.vivo.MODULOS[e.modulo] || e.modulo));
        li.appendChild(SC.el('span', 'actividad-titulo', SC.ortografia(e.titulo)));
        return li;
    }

    function mostrarError(mensaje) {
        error.textContent = mensaje;
        error.hidden = !mensaje;
    }

    function cargar() {
        botonMas.disabled = true;
        return SC.api('/actividad?limite=50' + (antesId ? '&antes_id=' + antesId : '')).then(function (r) {
            r.eventos.forEach(function (e) {
                lista.appendChild(fila(e));
                if (e.evento_id > ultimoId) { ultimoId = e.evento_id; }
            });
            antesId = r.antes_id;
            botonMas.hidden = !r.hay_mas;
            vacio.hidden = lista.children.length > 0;
            mostrarError('');
            if (conexion) { conexion.visto(ultimoId); }
        }).catch(function (e) {
            mostrarError(e.message);
        }).then(function () {
            botonMas.disabled = false;
        });
    }

    function situacion() {
        return SC.api('/actividad/resumen').then(function (r) {
            estado.textContent = SC.vivo.SITUACIONES[r.estado_simulador] +
                (r.dia_simulado ? ' · operación simulada hasta el ' + SC.fecha(r.dia_simulado) : '');
        }).catch(function () { estado.textContent = SC.vivo.SITUACIONES.SIN_CONEXION; });
    }

    function nuevo(e) {
        if (e.evento_id <= ultimoId) { return; }
        ultimoId = e.evento_id;
        var li = fila(e);
        li.classList.add('actividad-nueva');
        lista.insertBefore(li, lista.firstChild);
        vacio.hidden = true;
        if (e.tipo === 'SIMULACION_AL_DIA' || e.tipo === 'SIMULACION_REINICIADA' || e.tipo === 'VENTAS_DIA') {
            situacion();
        }
    }

    function reconectar() {
        SC.vaciar(lista);
        antesId = null;
        ultimoId = 0;
        situacion();
        cargar();
    }

    botonMas.addEventListener('click', cargar);
    situacion();
    cargar().then(function () {
        conexion = SC.vivo.escuchar(nuevo, reconectar, function (s) {
            estado.textContent = SC.vivo.SITUACIONES[s] || s;
        });
        conexion.visto(ultimoId);
    });
}(typeof window !== 'undefined' ? window.SC : undefined, typeof window !== 'undefined' ? window : globalThis));