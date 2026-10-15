/*
 * Actividad en vivo (CC-09 y CC-22, control de cambios, riesgo R6).
 *
 * - SC.vivo.escuchar(): conexion de Server-Sent Events con Tomcat (/api/eventos, CC-21);
 *   se reconecta sola y vuelve a sincronizar con /api/actividad/resumen al reconectar.
 * - Franja "En vivo" del Resumen ejecutivo (diseno CC-10), si la pagina la tiene.
 * Todo se inserta con textContent (prevencion de XSS); los textos de la base vienen en
 * ASCII (CC-11) y se muestran con acentos con SC.ortografia().
 */
(function (SC, global) {
    'use strict';
    if (!SC) { return; }
    var doc = global.document;

    var ETIQUETAS = {
        RECEPCION: 'A tiempo', RECEPCION_TARDIA: 'Tardío', RECEPCION_PARCIAL: 'Incompleto',
        ORDEN_EMITIDA: 'Orden', VENTAS_DIA: 'Cierre del día', ALERTA_KPI: 'Alerta',
        CASO_NUEVO: 'Caso nuevo', SIMULACION_AL_DIA: 'Al día', SIMULACION_REINICIADA: 'Reinicio'
    };
    var CLASE_SEVERIDAD = { INFO: 'estado-neutro', ATENCION: 'estado-atencion', CRITICO: 'estado-critico' };
    var MODULOS = {
        resumen: 'Resumen', compras: 'Compras', inventarios: 'Inventarios', logistica: 'Logística y transporte',
        almacenes: 'Almacenes', proveedores: 'Proveedores', ia: 'Inteligencia artificial', alertas: 'Alertas ejecutivas'
    };
    var SITUACIONES = {
        EN_VIVO: 'En vivo', AL_DIA: 'Al día', DETENIDO: 'Detenido', SIN_INICIAR: 'Sin iniciar',
        RECONECTANDO: 'Reconectando', SIN_CONEXION: 'Sin conexión'
    };

    /** Insignia con texto (no solo color) segun el tipo y la severidad del evento. */
    function insignia(e) {
        return SC.el('span', 'insignia ' + (CLASE_SEVERIDAD[e.severidad] || 'estado-neutro'),
            ETIQUETAS[e.tipo] || e.tipo);
    }

    /** "1 oct 12:00" con la fecha y hora simuladas del evento. */
    function cuando(e) {
        return SC.fecha(e.fecha_simulada, false) + ' ' + SC.hora(e.ocurrido);
    }

    /**
     * Abre la conexion en vivo. alEvento(evento) recibe cada evento nuevo, una sola vez;
     * alReconectar() se llama cuando la conexion vuelve, para sincronizar lo perdido;
     * alEstado(situacion) recibe RECONECTANDO o SIN_CONEXION.
     */
    function escuchar(alEvento, alReconectar, alEstado) {
        var fuente = null, abierta = false, reintento = null, ultimoId = 0;

        function abrir() {
            if (!global.EventSource) { alEstado('SIN_CONEXION'); return; }
            fuente = new global.EventSource(SC.CTX + '/api/eventos');
            fuente.addEventListener('evento', function (m) {
                var e;
                try { e = JSON.parse(m.data); } catch (x) { return; }
                if (!e || !(e.evento_id > ultimoId)) { return; }
                ultimoId = e.evento_id;
                alEvento(e);
            });
            fuente.addEventListener('open', function () {
                if (abierta) { alReconectar(); }
                abierta = true;
            });
            fuente.addEventListener('error', function () {
                if (fuente.readyState === global.EventSource.CLOSED) {
                    alEstado('SIN_CONEXION');            // 401 o 503: se reintenta en 30 segundos
                    if (!reintento) {
                        reintento = global.setTimeout(function () {
                            reintento = null;
                            abierta = true;
                            abrir();
                        }, 30000);
                    }
                } else {
                    alEstado('RECONECTANDO');
                }
            });
        }

        global.addEventListener('pagehide', function () {
            if (fuente) { fuente.close(); }                 // libera la conexion en Tomcat
        });
        abrir();
        return {
            visto: function (id) { if (id > ultimoId) { ultimoId = id; } }
        };
    }

    SC.vivo = {
        ETIQUETAS: ETIQUETAS, MODULOS: MODULOS, SITUACIONES: SITUACIONES,
        insignia: insignia, cuando: cuando, escuchar: escuchar
    };

    /* -------------------------------------------------- franja del Resumen ejecutivo */

    var franja = doc.getElementById('franja-vivo');
    if (!franja) { return; }
    var nodos = {
        estado: doc.getElementById('franja-estado'),
        hora: doc.getElementById('franja-hora'),
        titulo: doc.getElementById('franja-titulo'),
        insignia: doc.getElementById('franja-insignia'),
        contador: doc.getElementById('franja-contador')
    };
    var dia = null, eventosDia = 0, conexion = null, ultimoMostrado = 0;

    function situacion(s) {
        franja.setAttribute('data-estado', s);
        nodos.estado.textContent = SITUACIONES[s] || s;
    }

    function contador() {
        nodos.contador.textContent = 'Ver actividad (' + eventosDia + ' hoy)';
    }

    function mostrar(e) {
        SC.vaciar(nodos.insignia);
        if (!e) {
            nodos.hora.textContent = '';
            nodos.titulo.textContent = 'Sin actividad todavía: el simulador no se ha iniciado.';
            return;
        }
        nodos.hora.textContent = cuando(e);
        nodos.hora.setAttribute('datetime', e.ocurrido);
        nodos.titulo.textContent = SC.ortografia(e.titulo);
        nodos.insignia.appendChild(insignia(e));
    }

    function sincronizar() {
        return SC.api('/actividad/resumen').then(function (r) {
            situacion(r.estado_simulador);
            dia = r.dia_simulado;
            eventosDia = r.eventos_dia || 0;
            contador();
            mostrar(r.ultimo);
            ultimoMostrado = r.ultimo ? r.ultimo.evento_id : 0;
            if (conexion) { conexion.visto(ultimoMostrado); }
        }).catch(function () {
            situacion('SIN_CONEXION');
        });
    }

    function recibir(e) {
        if (e.evento_id <= ultimoMostrado) { return; }
        ultimoMostrado = e.evento_id;
        if (e.fecha_simulada !== dia) { dia = e.fecha_simulada; eventosDia = 0; }
        eventosDia += 1;
        contador();
        situacion(e.tipo === 'SIMULACION_AL_DIA' ? 'AL_DIA'
            : e.tipo === 'SIMULACION_REINICIADA' ? 'SIN_INICIAR' : 'EN_VIVO');
        mostrar(e);
        franja.classList.remove('franja-nueva');
        void franja.offsetWidth;                            // reinicia la animacion
        franja.classList.add('franja-nueva');
    }

    sincronizar().then(function () {
        conexion = escuchar(recibir, sincronizar, situacion);
        conexion.visto(ultimoMostrado);
    });
}(typeof window !== 'undefined' ? window.SC : undefined, typeof window !== 'undefined' ? window : globalThis));