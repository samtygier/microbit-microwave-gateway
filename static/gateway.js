
export async function call_wave(start, stop){
    const wave_start = document.getElementById("form_wave_start").value;
    const wave_stop = document.getElementById("form_wave_stop").value;
    console.log(`hello call_wave ${wave_start} -> ${wave_stop}`);

    const response = await fetch("/wave", {
        method: "POST",
        body: JSON.stringify({ start: wave_start, stop: wave_stop})
    });

}

