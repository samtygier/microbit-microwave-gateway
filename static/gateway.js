
export async function call_wave(){
    const wave_start = document.getElementById("form_wave_start").value;
    const wave_stop = document.getElementById("form_wave_stop").value;
    console.log(`call_wave ${wave_start} -> ${wave_stop}`);

    const response = await fetch("/wave", {
        method: "POST",
        body: JSON.stringify({ start: wave_start, stop: wave_stop})
    });
}

export async function call_set_config(config_name, form_name){
    const config_value = document.getElementById(form_name).value;
    console.log(`call_set_config ${config_name} ${config_value}`);

    const response = await fetch("/config", {
        method: "POST",
        body: `{"${config_name}": "${config_value}"}`
    });
}

export async function gateway_status_check(){
    fetch("/check", { signal: AbortSignal.timeout(2000) })
        .then(response => response.json())
        .then(function(result){
            document.getElementById("status_gateway").innerText = result['gateway']
        })
        .catch((error) => {
            document.getElementById("status_gateway").innerText = error
        });
}

export async function run_provision(){
    const row = document.getElementById("form_prov_row").value;
    const col = document.getElementById("form_prov_col").value;
    fetch("/prov", {
                method: "POST",
        body: `{"row": "${row}", "col": "${col}"}`
        })
        .then(response => response.json())
        .then(function(result){

        })
        .catch((error) => {

        });
}
