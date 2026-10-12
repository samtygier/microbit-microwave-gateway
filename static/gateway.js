
export async function call_wave(){
    const wave_start = document.getElementById("form_wave_start").value;
    const wave_stop = document.getElementById("form_wave_stop").value;
    console.log(`hello call_wave ${wave_start} -> ${wave_stop}`);

    const response = await fetch("/wave", {
        method: "POST",
        body: JSON.stringify({ start: wave_start, stop: wave_stop})
    });
}

export async function call_set_config(config_name, form_name){
    const config_value = document.getElementById(form_name).value;
    console.log(`hello call_set_config ${config_name} ${config_value}`);

    const response = await fetch("/config", {
        method: "POST",
        body: `{"${config_name}": "${config_value}"}`
    });
}

