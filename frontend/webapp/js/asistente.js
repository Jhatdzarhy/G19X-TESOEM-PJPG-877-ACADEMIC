/*
 * Asistente de IA (CC-17): chat de solo lectura sobre el motor analitico.
 *
 * Seguridad (OWASP, XSS): la respuesta del modelo se trata como texto no confiable.
 * Nunca se usa innerHTML; el texto se divide en bloques y se construye con nodos:
 * solo se reconocen **negritas**, listas con viñetas (-, *), listas numeradas (1.),
 * tablas con | y separadores ---. Cada celda y cada texto es un nodo de texto, así
 * que cualquier etiqueta HTML que escriba el modelo se muestra literalmente.
 *
 * Cada respuesta muestra siempre el modelo que respondió, la fecha de corte de los
 * datos, las consultas al motor y el aviso de que la IA puede equivocarse.
 */
(function () {
    'use strict';

    var SC = window.SC;
    var AVISO = 'La IA puede equivocarse; verifica las cifras en el dashboard. Datos operativos simulados.';
    var HERRAMIENTAS = {
        consultar_kpis: 'KPIs',
        consultar_estaciones: 'Estado de la cadena',
        consultar_recomendaciones: 'Recomendaciones',
        consultar_recomendacion: 'Detalle de recomendación',
        consultar_riesgo_proveedores: 'Riesgo de proveedores',
        consultar_pronostico: 'Pronóstico',
        consultar_anomalias: 'Anomalías',
        consultar_glosario: 'Glosario de KPIs'
    };
    var estado = { conversacion: null, enviando: false };

    function $(id) { return document.getElementById(id); }

    /* ------------------------------------------------- Markdown mínimo y seguro */

    /** Agrega texto con **negritas** a un nodo, sin interpretar HTML. */
    function agregarEnLinea(nodo, texto) {
        var partes = String(texto).split(/(\*\*[^*\n]+\*\*)/g);
        partes.forEach(function (p) {
            if (!p) { return; }
            if (/^\*\*[^*\n]+\*\*$/.test(p)) {
                nodo.appendChild(SC.el('strong', null, p.slice(2, -2)));
            } else {
                nodo.appendChild(document.createTextNode(p.replace(/\*\*/g, '')));
            }
        });
    }

    var VINETA = /^\s*[-*•]\s+(.*)$/;
    var NUMERO = /^\s*(\d{1,3})[.)]\s+(.*)$/;
    var TITULO = /^\s*#{1,6}\s+(.*)$/;
    var SEPARADOR = /^\s*([-*_])(\s*\1){2,}\s*$/;
    var FILA_TABLA = /^\s*\|.*\|\s*$/;
    var REGLA_TABLA = /^\s*\|?(\s*:?-{2,}:?\s*\|)+\s*:?-{0,}:?\s*\|?\s*$/;

    function celdas(linea) {
        var partes = linea.trim().replace(/^\|/, '').replace(/\|$/, '').split('|');
        return partes.map(function (c) { return c.trim(); });
    }

    /** Convierte la respuesta en nodos: párrafos, listas, tablas, separadores y negritas. Nada más. */
    function renderizar(texto) {
        var fragmento = document.createDocumentFragment();
        var lineas = String(texto || '').replace(/\r\n?/g, '\n').split('\n');
        var lista = null, tipoLista = null, parrafo = null, tabla = null;

        function cerrarParrafo() { parrafo = null; }
        function cerrarLista() { lista = null; tipoLista = null; }
        function cerrarTabla() { tabla = null; }
        function siguienteNoVacia(i) {
            for (var j = i + 1; j < lineas.length; j++) { if (lineas[j].trim()) { return lineas[j]; } }
            return '';
        }

        lineas.forEach(function (linea, i) {
            var m;
            if (FILA_TABLA.test(linea)) {
                cerrarParrafo();
                cerrarLista();
                if (REGLA_TABLA.test(linea)) { return; }   // fila |---|---| de la tabla
                if (!tabla) {
                    var envoltura = SC.el('div', 'md-tabla');
                    tabla = SC.el('table');
                    envoltura.appendChild(tabla);
                    fragmento.appendChild(envoltura);
                    var encabezado = SC.el('tr');
                    celdas(linea).forEach(function (c) {
                        var th = SC.el('th');
                        th.scope = 'col';
                        agregarEnLinea(th, c);
                        encabezado.appendChild(th);
                    });
                    tabla.appendChild(SC.el('thead')).appendChild(encabezado);
                    tabla.appendChild(SC.el('tbody'));
                    return;
                }
                var tr = SC.el('tr');
                celdas(linea).forEach(function (c) {
                    var td = SC.el('td');
                    agregarEnLinea(td, c);
                    tr.appendChild(td);
                });
                tabla.lastChild.appendChild(tr);
                return;
            }
            cerrarTabla();
            if (SEPARADOR.test(linea)) {
                cerrarParrafo();
                cerrarLista();
                fragmento.appendChild(SC.el('hr', 'md-separador'));
                return;
            }
            if (!linea.trim()) {
                cerrarParrafo();
                // Una lista numerada separada por líneas en blanco sigue siendo la misma lista.
                var sig = siguienteNoVacia(i);
                if (!(tipoLista === 'ol' && NUMERO.test(sig)) && !(tipoLista === 'ul' && VINETA.test(sig))) { cerrarLista(); }
                return;
            }
            if ((m = linea.match(NUMERO))) {
                cerrarParrafo();
                if (tipoLista !== 'ol') { lista = SC.el('ol', 'md-lista'); tipoLista = 'ol'; fragmento.appendChild(lista); }
                var li = SC.el('li');
                li.value = Number(m[1]);
                agregarEnLinea(li, m[2]);
                lista.appendChild(li);
                return;
            }
            if ((m = linea.match(VINETA))) {
                cerrarParrafo();
                if (tipoLista !== 'ul') { lista = SC.el('ul', 'md-lista'); tipoLista = 'ul'; fragmento.appendChild(lista); }
                var li2 = SC.el('li');
                agregarEnLinea(li2, m[1]);
                lista.appendChild(li2);
                return;
            }
            if (lista && /^\s{2,}\S/.test(linea)) {
                // Continuación con sangría del último elemento de la lista.
                var ultimo = lista.lastChild;
                ultimo.appendChild(document.createTextNode(' '));
                agregarEnLinea(ultimo, linea.trim());
                return;
            }
            cerrarLista();
            if ((m = linea.match(TITULO))) {
                cerrarParrafo();
                var t = SC.el('p', 'md-titulo');
                agregarEnLinea(t, m[1].replace(/\*\*/g, ''));
                fragmento.appendChild(t);
                return;
            }
            if (!parrafo) { parrafo = SC.el('p'); fragmento.appendChild(parrafo); }
            else { parrafo.appendChild(SC.el('br')); }
            agregarEnLinea(parrafo, linea);
        });
        return fragmento;
    }

    /* ---------------------------------------------------------------- mensajes */

    function textoHerramientas(herramientas) {
        if (!herramientas || !herramientas.length) { return ''; }
        var nombres = [];
        herramientas.forEach(function (h) {
            var n = HERRAMIENTAS[h.herramienta] || SC.ortografia(String(h.herramienta || '').replace(/^consultar_/, '').replace(/_/g, ' '));
            if (nombres.indexOf(n) < 0) { nombres.push(n); }
        });
        return 'Consultó: ' + nombres.join(', ');
    }

    function agregarMensaje(m) {
        $('asis-bienvenida').hidden = true;
        var esUsuario = m.rol === 'USUARIO';
        var li = SC.el('li', 'asis-mensaje ' + (esUsuario ? 'asis-usuario' : 'asis-asistente'));
        li.appendChild(SC.el('span', 'visualmente-oculto', esUsuario ? 'Tú dijiste:' : 'El asistente respondió:'));
        var burbuja = SC.el('div', 'asis-burbuja');
        if (esUsuario) {
            burbuja.appendChild(SC.el('p', null, m.contenido));
        } else {
            burbuja.appendChild(renderizar(SC.ortografia(m.contenido)));
        }
        li.appendChild(burbuja);

        if (!esUsuario) {
            var meta = SC.el('div', 'asis-meta');
            var verificado = m.verificado !== undefined ? m.verificado : !!(m.herramientas && m.herramientas.length);
            meta.appendChild(verificado
                ? SC.el('span', 'insignia estado-ok', '✓ Cifras del motor analítico')
                : SC.el('span', 'insignia estado-atencion', '! Sin consultas al motor: verifica la respuesta'));
            meta.appendChild(SC.el('span', null, 'Respondió: ' + (m.modelo || 'modelo no identificado')));
            meta.appendChild(SC.el('span', null, 'Datos al ' + SC.fecha(m.fecha_corte)));
            var herr = textoHerramientas(m.herramientas);
            if (herr) { meta.appendChild(SC.el('span', null, herr)); }
            li.appendChild(meta);
            li.appendChild(SC.el('p', 'asis-aviso-mensaje', m.aviso || AVISO));
        } else if (m.fecha) {
            li.appendChild(SC.el('span', 'asis-hora', SC.hora(m.fecha)));
        }
        $('asis-mensajes').appendChild(li);
        li.scrollIntoView({ block: 'nearest' });
        return li;
    }

    function limpiarChat() {
        SC.vaciar($('asis-mensajes'));
        $('asis-bienvenida').hidden = false;
        $('asis-error').hidden = true;
    }

    /* ------------------------------------------------------------- historial */

    function cargarHistorial() {
        return SC.api('/asistente/conversaciones').then(function (datos) {
            var ul = $('asis-conversaciones');
            SC.vaciar(ul);
            var lista = datos.conversaciones || [];
            $('asis-sin-historial').hidden = lista.length > 0;
            lista.forEach(function (c) {
                var li = SC.el('li');
                var b = SC.el('button', 'asis-conversacion');
                b.type = 'button';
                b.setAttribute('aria-pressed', c.conversacion_id === estado.conversacion ? 'true' : 'false');
                b.appendChild(SC.el('span', 'asis-conversacion-titulo', SC.ortografia(c.titulo)));
                b.appendChild(SC.el('span', 'asis-conversacion-sub', SC.fecha(c.fecha_actualizacion) + ' ' +
                    SC.hora(c.fecha_actualizacion) + ' · ' + c.mensajes + (c.mensajes === 1 ? ' mensaje' : ' mensajes')));
                b.addEventListener('click', function () { abrirConversacion(c.conversacion_id); });
                li.appendChild(b);
                ul.appendChild(li);
            });
        }).catch(mostrarError);
    }

    function abrirConversacion(id) {
        return SC.api('/asistente/conversaciones/' + encodeURIComponent(id)).then(function (datos) {
            estado.conversacion = datos.conversacion_id;
            limpiarChat();
            (datos.mensajes || []).forEach(agregarMensaje);
            if (!(datos.mensajes || []).length) { $('asis-bienvenida').hidden = false; }
            cargarHistorial();   // marca la conversación abierta
            $('asis-pregunta').focus();
        }).catch(mostrarError);
    }

    /* ----------------------------------------------------------------- envío */

    function ocupado(si) {
        estado.enviando = si;
        $('asis-enviar').disabled = si;
        $('asis-pregunta').disabled = si;
        document.querySelectorAll('.asis-sugerencia').forEach(function (b) { b.disabled = si; });
    }

    function enviar(texto) {
        var pregunta = String(texto || '').trim();
        if (!pregunta || estado.enviando) { return; }
        if (pregunta.length > 1000) {
            mostrarError({ message: 'La pregunta no debe pasar de 1000 caracteres.' });
            return;
        }
        $('asis-error').hidden = true;
        agregarMensaje({ rol: 'USUARIO', contenido: pregunta });
        $('asis-pregunta').value = '';
        actualizarContador();
        var espera = SC.el('li', 'asis-mensaje asis-asistente asis-pensando');
        espera.appendChild(SC.el('div', 'asis-burbuja', 'Consultando el motor analítico…'));
        $('asis-mensajes').appendChild(espera);
        espera.scrollIntoView({ block: 'nearest' });
        ocupado(true);

        SC.enviar('/asistente/mensajes', { mensaje: pregunta, conversacion_id: estado.conversacion })
            .then(function (r) {
                espera.remove();
                estado.conversacion = r.conversacion_id;
                agregarMensaje({
                    rol: 'ASISTENTE', contenido: r.respuesta, modelo: r.modelo, herramientas: r.herramientas,
                    verificado: r.verificado, fecha_corte: r.fecha_corte, aviso: r.aviso
                });
                cargarHistorial();
            })
            .catch(function (err) {
                espera.remove();
                mostrarError(err);
                $('asis-pregunta').value = pregunta;
                actualizarContador();
            })
            .then(function () {
                ocupado(false);
                $('asis-pregunta').focus();
            });
    }

    function actualizarContador() {
        $('asis-contador').textContent = $('asis-pregunta').value.length + ' / 1000';
    }

    function mostrarError(err) {
        if (err && err.estado === 401) { return; }
        var aviso = $('asis-error');
        aviso.textContent = (err && err.message) || 'No se pudo completar la solicitud.';
        aviso.hidden = false;
    }

    /* ---------------------------------------------------------------- inicio */

    function cargarSugerencias() {
        SC.api('/asistente/sugerencias').then(function (datos) {
            var caja = $('asis-sugerencias');
            SC.vaciar(caja);
            (datos.sugerencias || []).forEach(function (s) {
                var b = SC.el('button', 'asis-sugerencia', s);
                b.type = 'button';
                b.addEventListener('click', function () { enviar(s); });
                caja.appendChild(b);
            });
        }).catch(function () { /* sin sugerencias: el chat sigue disponible */ });
    }

    function cargarEstado() {
        SC.api('/asistente/estado').then(function (datos) {
            var nombres = (datos.proveedores || []).filter(function (p) { return p.configurado; })
                .map(function (p) { return p.nombre; });
            $('asis-modelos').textContent = nombres.length
                ? 'Modelos gratuitos en orden de respaldo: ' + nombres.join(', ') + '. Límite: ' +
                  datos.limite_mensajes_por_minuto + ' preguntas por minuto.'
                : 'No hay modelos de IA configurados.';
        }).catch(function () { /* el estado es informativo */ });
    }

    $('asis-formulario').addEventListener('submit', function (e) {
        e.preventDefault();
        enviar($('asis-pregunta').value);
    });
    $('asis-pregunta').addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
            e.preventDefault();
            enviar($('asis-pregunta').value);
        }
    });
    $('asis-pregunta').addEventListener('input', actualizarContador);
    $('asis-nueva').addEventListener('click', function () {
        estado.conversacion = null;
        limpiarChat();
        cargarHistorial();
        $('asis-pregunta').focus();
    });

    cargarSugerencias();
    cargarEstado();
    cargarHistorial();

    window.SC_ASISTENTE = { renderizar: renderizar };
}());