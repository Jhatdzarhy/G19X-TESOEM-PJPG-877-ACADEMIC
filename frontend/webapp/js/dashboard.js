const API_BASE = "http://localhost:8000";

async function cargarAlertas() {
    const res = await fetch(`${API_BASE}/kpis/alertas`);
    const data = await res.json();
    const alertas = data.alertas;

    const contenedor = document.getElementById("contenedor-alertas");
    contenedor.innerHTML = "";

    if (alertas.length === 0) {
        contenedor.innerHTML = `<div class="alert alert-success mb-0">✅ No hay alertas activas. Todos los indicadores dentro de rango.</div>`;
        return;
    }

    alertas.forEach(a => {
        const claseAlerta = a.severidad === "alta" ? "alert-danger" : "alert-warning";
        const div = document.createElement("div");
        div.className = `alert ${claseAlerta} mb-2`;
        div.innerHTML = `<strong>[${a.tipo}]</strong> ${a.mensaje}`;
        contenedor.appendChild(div);
    });
}

async function cargarOTIF() {
    const res = await fetch(`${API_BASE}/kpis/otif`);
    const data = await res.json();
    document.getElementById("kpi-otif").textContent = data.otif_pct + "%";
    document.getElementById("kpi-otif-detalle").textContent =
        `${data.entregas_a_tiempo} de ${data.total_entregadas} entregas a tiempo`;
}

async function cargarLeadTime() {
    const res = await fetch(`${API_BASE}/kpis/lead-time`);
    const data = await res.json();
    document.getElementById("kpi-leadtime").textContent = data.lead_time_dias_promedio;
}

async function cargarProveedores() {
    const res = await fetch(`${API_BASE}/kpis/proveedores`);
    const data = await res.json();
    const proveedores = data.proveedores;

    document.getElementById("kpi-proveedores-count").textContent = proveedores.length;

    const tbody = document.querySelector("#tabla-proveedores tbody");
    tbody.innerHTML = "";
    proveedores.forEach(p => {
        const fila = document.createElement("tr");
        fila.innerHTML = `<td>${p.nombre}</td><td>${p.pais}</td><td>${p.calificacion}</td>`;
        tbody.appendChild(fila);
    });

    const ctx = document.getElementById("chartProveedores");
    new Chart(ctx, {
        type: "bar",
        data: {
            labels: proveedores.map(p => p.nombre),
            datasets: [{
                label: "Calificación",
                data: proveedores.map(p => p.calificacion),
                backgroundColor: "rgba(13, 110, 253, 0.7)"
            }]
        },
        options: {
            scales: { y: { beginAtZero: true, max: 5 } }
        }
    });
}

async function cargarInventario() {
    const res = await fetch(`${API_BASE}/kpis/inventario`);
    const data = await res.json();
    const inventario = data.inventario;

    const tbody = document.querySelector("#tabla-inventario tbody");
    tbody.innerHTML = "";
    inventario.forEach(p => {
        const fila = document.createElement("tr");
        const claseStock = p.stock_actual <= 0 ? "table-danger" : "";
        fila.className = claseStock;
        fila.innerHTML = `<td>${p.sku}</td><td>${p.nombre}</td><td>${p.total_entradas}</td><td>${p.total_salidas}</td><td>${p.stock_actual}</td>`;
        tbody.appendChild(fila);
    });
}

async function cargarEnvios() {
    const res = await fetch(`${API_BASE}/kpis/envios`);
    const data = await res.json();
    const envios = data.envios;

    const tbody = document.querySelector("#tabla-envios tbody");
    tbody.innerHTML = "";

    envios.forEach(e => {
        const badgeClass = e.estado === "A tiempo" ? "bg-success" : "bg-danger";
        const fila = document.createElement("tr");
        fila.innerHTML = `
            <td>${e.proveedor}</td>
            <td>${e.fecha_salida}</td>
            <td>${e.fecha_llegada_estim}</td>
            <td>${e.fecha_llegada_real}</td>
            <td>$${e.costo_flete}</td>
            <td><span class="badge ${badgeClass}">${e.estado}</span></td>
        `;
        tbody.appendChild(fila);
    });
}

async function cargarAlmacenes() {
    const res = await fetch(`${API_BASE}/kpis/almacenes`);
    const data = await res.json();
    const almacenes = data.almacenes;

    const tbody = document.querySelector("#tabla-almacenes tbody");
    tbody.innerHTML = "";
    almacenes.forEach(a => {
        const fila = document.createElement("tr");
        fila.innerHTML = `<td>${a.nombre}</td><td>${a.ubicacion}</td><td>${a.unidades_almacenadas}</td>`;
        tbody.appendChild(fila);
    });
}

document.addEventListener("DOMContentLoaded", () => {
    cargarAlertas();
    cargarOTIF();
    cargarLeadTime();
    cargarProveedores();
    cargarInventario();
    cargarEnvios();
    cargarAlmacenes();
});