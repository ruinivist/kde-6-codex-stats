// Formats token counts and dollar estimates for the widget's two displays.
// Imported by the root QML and exercised by the formatting checks.

.pragma library

// ---------- Display formatting ----------

function compact(value) {
    if (value === null || value === undefined)
        return "--";
    const units = ["", "K", "Mil", "Bil", "Tri"];
    let index = 0;
    while (value >= 1000 && index < units.length - 1) {
        value /= 1000;
        index++;
    }
    let rounded = Math.round(value * 10) / 10;
    if (rounded >= 1000 && index < units.length - 1) {
        rounded /= 1000;
        index++;
    }
    return rounded.toFixed(1).replace(/\.0$/, "") + units[index];
}

function grouped(value) {
    return value === null || value === undefined ? "--" : String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function dollars(value) {
    return value === null || value === undefined ? "--" : "$" + value.toFixed(2);
}
