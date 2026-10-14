
export async function call_wave(){
    let data = {}
    data["row"] = document.getElementById("form_wave_row").value;
    data["start"] = document.getElementById("form_wave_start").value;
    data["stop"] = document.getElementById("form_wave_stop").value;
    data["delay"] = document.getElementById("form_wave_delay").value;
    console.log(`call_wave ${data}`);

    const response = await fetch("/wave", {
        method: "POST",
        body: JSON.stringify(data)
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
            let element = document.getElementById("prov_log")
            element.value += "\n" + result['result']
            element.selectionStart = element.value.length; // Todo make it scroll to end?
        })
        .catch((error) => {

        });
}

export async function send_provision(){
    const response = await fetch("/prov_send", { });
}