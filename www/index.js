/**
 * Create HTML element, setting classes, other attribures, text, and children.
 * @param  {string} type
 * DOM element type
 * @param  {string[]} classes=[]
 * Classes to apply to element
 * @param  {Object.<string, string>} attributes={}
 * Map of attribute name to value
 * @param  {string} iText=""
 * innerText of element (HTML escaped by browser)
 * @param  {HTMLElement[]} children=[]
 * Array of children
 * @returns {HTMLElement}
 * The created element
 */
function createElem(type, classes = [], attributes = {}, listeners = {}, iText = "", children = []) {
    //Create elem
    let elem = document.createElement(type);
    //Add classes
    elem.classList.add(...classes);
    //Apply attributes
    for (let attname in attributes) {
        elem.setAttribute(attname, attributes[attname]);
    }
    //Apply listeners
    for (let listname in listeners) {
        elem.addEventListener(listname, listeners[listname]);
    }
    //Inner text
    elem.innerText = iText;
    //Childten
    for (let child in children) {
        elem.appendChild(children[child]);
    }
    return elem;
}
function timeout(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
function format_float(f) {
    if (f === null) {
        return "null"
    }
    return f.toFixed(4);
}
function calc_crow(pos1, pos2) {
    const deg2rad = (Value) => {
        return Value * Math.PI / 180;
    }
    let R = 6371e3; // km
    let dLat = deg2rad(pos2[0] - pos1[0]);
    let dLon = deg2rad(pos2[1] - pos1[1]);
    let lat1 = deg2rad(pos1[0]);
    let lat2 = deg2rad(pos2[0]);

    let a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.sin(dLon / 2) * Math.sin(dLon / 2) * Math.cos(lat1) * Math.cos(lat2);
    let c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
}

let global_gps = {
    position: [undefined, undefined],
    listener: undefined,
    timestamp: undefined,
    accuracy: undefined
};
function format_gps(position) {
    return position[0] + "," + position[1];
};

let waiter = (ws, button_names, checkbox_id) => {
    let handle_active = false;
    let handle_type = undefined
    let handle_cookie = undefined;

    let root_elem = createElem("div", ["waiter-root"], {}, {}, "", []);

    let buttons = [];
    let checkbox = undefined;
    let checkbox_full = undefined;
    let auto_button = undefined;

    let handle_click = (id) => {
        if (handle_active) {
            ws.send(JSON.stringify({
                "type": handle_type,
                "data": {
                    "type": "click",
                    "cookie": handle_cookie,
                    "result": id
                }
            }));
        }
    };

    let handle_auto = (id) => {
        console.log("Sending auto");
        ws.send(JSON.stringify({
            "type": handle_type,
            "data": {
                "type": "auto",
                "key": checkbox.checked ? id : null
            }
        }));
    };


    let add_type = (button_name) => {
        let button_elem = createElem(
            "button", [], {}, { "click": () => handle_click(button_name.id) }, button_name.name
        );
        buttons.push(button_elem);

        if (button_name.id === checkbox_id) {
            auto_button = button_elem;
            checkbox = createElem("input", ["waiter-button"], { 'type': "checkbox" }, { "change": () => handle_auto(button_name.id) });
            checkbox_full = createElem("div", ["waiter-auto-checkbox"], {}, {}, "", [
                checkbox,
                createElem("label", ["waiter-auto-label"], {}, {}, "Auto " + button_name.name)
            ]);
        }

        return button_elem;
    };

    button_names.forEach(add_type);

    root_elem.appendChild(createElem("div", ["watier-buttons"], {}, {}, "", buttons));

    if (checkbox_full !== undefined) {
        root_elem.appendChild(checkbox_full);
    }

    let on_message = (content) => {
        handle_type = content.type;
        if (content.waiting) {
            buttons.forEach(elem => {
                elem.disabled = false;
            });
            handle_cookie = content.waiting_cookie;
            handle_active = true;
        } else {
            handle_active = false;
            buttons.forEach(elem => {
                elem.disabled = true;
            });
        }
        if (checkbox != undefined) {
            let new_checked = (checkbox_id == content.auto_key);
            if (checkbox.checked != new_checked) {
                checkbox.checked = new_checked;
            }
        }
    };

    return {
        elem: root_elem,
        on_message: on_message,
        add_type: add_type
    };
};

const BS_STATE_NAMES = {
    1: "A1",
    2: "A2",
    4: "B1",
    8: "B2",
    16: "C1",
    32: "C2",
    64: "D1",
    128: "D2",
    256: "E",
    512: "F",
};


let reveal_ui = () => {
    document.getElementById("main_alt").style.display = "none";
    document.getElementById("main_ui").style.display = "initial";
};

let hide_ui = () => {
    document.getElementById("main_alt").style.display = "initial";
    document.getElementById("main_alt").innerHTML = "No websocket connection to server. <a href='" + ("https://" + location.hostname + ":8081/") + "'>Click here to activate WS certificate</a>";
    document.getElementById("main_ui").style.display = "none";
    document.getElementById("main_ui").innerHTML = ""; //Wipe
    console.log("UI Wiped");
};

let reveal_sub_ui = () => {
    document.getElementById("sub_alt").style.display = "none";
    document.getElementById("sub_ui").style.display = "initial";
};

let hide_sub_ui = () => {
    document.getElementById("sub_alt").style.display = "initial";
    document.getElementById("sub_alt").innerHTML = "No internal websocket connection to server.";
    document.getElementById("sub_ui").style.display = "none";
    document.getElementById("sub_ui").innerHTML = ""; //Wipe
};


const SLAC_STATE_NAMES = ["Start Wait", "Reset", "Wipe NMK", "Param Req", "Start Atten", "Sounding", "Atten Char", "Select", "Match", "Set NMK", "Connect", "Done"];
const SLAC_DONENESS_NAMES = ["Running", "Done"];

const TASK_STATE_CHARS = ["?", "🔃", "✅", "❌", "❗", "D", "R"];
let state_task = (ws, root_elem, tasks, data, button) => {
    let elem = {
        "root": undefined,
        "name": undefined,
        "state": undefined,
        "manual": undefined,
        "children": undefined
    }
    elem.root = createElem("div", ["task-entry"], {}, {}, "", [
        createElem("div", ["task-hdr"], {}, {}, "", [
            elem.state = createElem("div", ["task-state"], {}, {}, "", []),
            elem.name = createElem("div", ["task-name"], {}, {}, data.name, []),
            elem.manual = button
        ]),
        elem.children = createElem("div", ["task-children"], {}, {}, "", [])
    ]);

    if (data.parent_name !== null) {
        tasks[data.parent_name].elem.children.appendChild(elem.root);
    } else {
        root_elem.appendChild(elem.root);
    }

    let set_state = (state) => {
        elem.state.innerText = TASK_STATE_CHARS[state];
    };

    set_state(data.result);

    let on_message = (content) => {
        set_state(content.result);
    };

    return {
        "elem": elem,
        "on_message": on_message
    };
};

let connect_ev = (mock_ws) => {

    let elements = {
        "waiter_start": undefined,
        "waiter_done": undefined,
        "waiter_plug": undefined,
        "bs": undefined,
        "slac": {
            "state": undefined,
            "result": undefined
        },
        "sdp": {
            "result": undefined
        },
        "proto": {
            "result": undefined
        },
        "v2g": {
            "result": undefined
        },
        "tasks_root": undefined,
        "tasks": {}
    };


    mock_ws.onopen = () => {
        document.getElementById("sub_alt").innerText = "Connected, loading";

        //Create elements

        //Name
        document.getElementById("sub_ui").appendChild(
            createElem("div", ["exp-ctrl"], {}, {}, "",
                [(elements.waiter_start = waiter(mock_ws, [
                    { id: "start_all", name: "Start All" },
                    { id: "start_man", name: "Start Manual" },
                    { id: "exit", name: "Exit" }], "start_all")).elem,
                (elements.waiter_done = waiter(mock_ws, [
                    { id: "done", name: "Done" }], "done")).elem
                ]
            )
        );

        //Connect wait
        document.getElementById("sub_ui").appendChild(
            createElem("div", [], {}, {}, "",
                [(elements.waiter_plug = waiter(mock_ws, [{ id: "plug", name: "Plug" }], "plug")).elem]
            ));

        //Basic signalling
        document.getElementById("sub_ui").appendChild(
            elements.bs = createElem("div", ["bs"])
        );

        //Basic slac
        document.getElementById("sub_ui").appendChild(
            createElem("div", ["slac"], {}, {}, "", [
                elements.slac.state = createElem("div", []),
                elements.slac.result = createElem("div", [])
            ]
            ));

        //SDP
        document.getElementById("sub_ui").appendChild(
            elements.sdp.result = createElem("div", ["sdp"])
        );

        //Proto
        document.getElementById("sub_ui").appendChild(
            elements.proto.result = createElem("div", ["v2g"])
        );

        //V2G
        document.getElementById("sub_ui").appendChild(
            elements.v2g.result = createElem("div", ["v2g"])
        );

        //Tasks root
        document.getElementById("sub_ui").appendChild(
            elements.tasks_root = createElem("div", ["tasks"])
        );
    };

    mock_ws.onmessage = (content) => {
        switch (content.type) {
            case "init_done":
                reveal_sub_ui();
                break;
            case "init_tasks":
                content.tasks.forEach(data => {
                    elements.tasks[data.name] = state_task(mock_ws, elements.tasks_root, elements.tasks, data, elements.waiter_done.add_type({
                        id: data.name,
                        name: "Start"
                    }));
                });
                break;
            case "task":
                console.log(content.name);
                elements.tasks[content.name].on_message(content);
                break;
            case "waiter_start":
                elements.waiter_start.on_message(content);
                break;
            case "waiter_done":
                elements.waiter_done.on_message(content);
                break;
            case "waiter_plug":
                elements.waiter_plug.on_message(content);
                break;
            case "basic_signaling":
                elements.bs.innerText = BS_STATE_NAMES[content.state.s] + ": " +
                    format_float(content.state.l) + " - " + format_float(content.state.h) + " @ " + format_float(content.state.d * 100) + "%, PP: " + format_float(content.state.p);
                break;
            case "SLAC_State":
                elements.slac.state.innerText = SLAC_STATE_NAMES[content.state] + " - " + SLAC_DONENESS_NAMES[content.state_done ? 1 : 0];
                break;
            case "SLAC_Result":
                elements.slac.result.innerText = JSON.stringify(content.result);
                break;
            case "SDP_Result":
                elements.sdp.result.innerText = JSON.stringify(content.result);
                break;
            case "Proto":
                elements.proto.result.innerText = JSON.stringify(content.result);
                break;
            case "V2G":
                elements.v2g.result.innerText = JSON.stringify(content.result);
                break;
            default:
                console.error("Unknown message type", content.type);
        }
    };

    mock_ws.onclose = () => {
        console.log("Socket closed");
        hide_sub_ui();
    };
};

let connect_main = (resolve, reject) => {
    let elements = {
        "name": {
            "name": undefined,
            "box": undefined,
            "plug": undefined,
            "gps": undefined
        },
        "process_state": undefined
    };

    let state_data = {
        gps: [undefined, undefined],
        running: false
    };

    let mock_ws = undefined;
    let poll_task_run = true;

    let ws = new WebSocket("wss://" + location.hostname + ":8081/");
    setTimeout(() => {
        if (ws.readyState != WebSocket.OPEN) {
            ws.close();
        }
    }, 2000);
    //let ws = new WebSocket("ws://localhost:8081/");
    ws.onopen = () => {
        document.getElementById("main_alt").innerText = "Connected, loading";

        //Create elements

        //Name
        document.getElementById("main_ui").appendChild(
            createElem("div", ["chg"], {}, {}, "", [
                createElem("div", [], {}, {}, "", [
                    elements.name.name = createElem("input", ["chg-name"], { "placeholder": "Name" }, {
                        "change": () => {
                            ws.send(JSON.stringify({
                                "type": "info",
                                "data": {
                                    "type": "name",
                                    "name": elements.name.name.value
                                }
                            }));
                        }
                    }),
                    elements.name.box = createElem("input", ["chg-name"], { "placeholder": "Box" }, {
                        "change": () => {
                            ws.send(JSON.stringify({
                                "type": "info",
                                "data": {
                                    "type": "box",
                                    "box": elements.name.box.value
                                }
                            }));
                        }
                    }),
                    elements.name.plug = createElem("input", ["chg-name"], { "placeholder": "Plug" }, {
                        "change": () => {
                            ws.send(JSON.stringify({
                                "type": "info",
                                "data": {
                                    "type": "plug",
                                    "plug": elements.name.plug.value
                                }
                            }));
                        }
                    }),
                ]),
                createElem("div", ["chg"], {}, {}, "", [
                    elements.name.gps = createElem("span", [], {}, {}, "", []),
                    createElem("button", ["chg-setpos"], {}, {
                        "click": () => {
                            if (global_gps !== undefined) {
                                ws.send(JSON.stringify({
                                    "type": "info",
                                    "data": {
                                        "type": "gps",
                                        "gps": global_gps.position
                                    }
                                }));
                            }
                        }
                    }, "Set position"),
                ])
            ])
        );
        document.getElementById("main_ui").appendChild(
            createElem("div", ["subprocess"], {}, {}, "", [
                createElem("button", ["subprocess-command"], {}, {
                    "click": () => {
                        ws.send(JSON.stringify({
                            "type": "process",
                            "data": {
                                "type": "start"
                            }
                        }));
                    }
                }, "Start"),
                createElem("button", ["subprocess-command"], {}, {
                    "click": () => {
                        ws.send(JSON.stringify({
                            "type": "process",
                            "data": {
                                "type": "sigint"
                            }
                        }));
                    }
                }, "SIG INT"),
                createElem("button", ["subprocess-command"], {}, {
                    "click": () => {
                        ws.send(JSON.stringify({
                            "type": "process",
                            "data": {
                                "type": "sigterm"
                            }
                        }));
                    }
                }, "SIG TERM"),
                createElem("button", ["subprocess-command"], {}, {
                    "click": () => {
                        ws.send(JSON.stringify({
                            "type": "process",
                            "data": {
                                "type": "sigkill"
                            }
                        }));
                    }
                }, "SIG KILL"),
                elements.process_state = createElem("span", ["subprocess-state"], {}, {}, "", [])
            ])
        );
        document.getElementById("main_ui").appendChild(
            createElem("div", [], {"id": "sub_ui", "style": "display: none;"})
        );
        document.getElementById("main_ui").appendChild(
            createElem("div", [], {"id": "sub_alt", "style": "display: initial;"}, {}, "")
        );
        hide_sub_ui();

        global_gps.listener = () => {
            elements.name.gps.innerText = `${format_gps(state_data.gps)} (${format_float(calc_crow(state_data.gps, global_gps.position))} m away)`
        };
        global_gps.listener(global_gps);

        (async () => {
            console.log("Start forward");
            while (poll_task_run) {
                if(state_data.running && (mock_ws == undefined)) {
                    console.log("Reconnecting forward");
                    mock_ws = {
                        "onopen": undefined,
                        "onmessage": undefined,
                        "onclose": undefined,
                        "send": (str) => {ws.send(JSON.stringify({
                            "type": "forward",
                            "data": JSON.parse(str)
                        }))}
                    };
                    ws.send(JSON.stringify({
                        "type": "forward_open"
                    }));
                }
                await new Promise((resolve) => setTimeout(resolve, 1000));
            }
        })();
    };

    ws.onmessage = (e) => {
        let content = JSON.parse(e.data);
        console.log(content);
        switch (content.type) {
            case "init_done":
                reveal_ui();
                break;
            case "info":
                elements.name.name.value = content.name;
                elements.name.box.value = content.box;
                elements.name.plug.value = content.plug;
                if (content.gps != undefined) {
                    state_data.gps = content.gps;
                    if (global_gps.listener != undefined) {
                        global_gps.listener();
                    }
                }
                break;
            case "process":
                state_data.running = content.running;
                elements.process_state.innerText = `EV ${state_data.running ? "ON" : "OFF"}`;
                break;
            case "forward_success":
                if (mock_ws != undefined) {
                    (connect_ev)(mock_ws);
                    mock_ws.onopen();
                }
                break;
            case "forward":
                if (mock_ws != undefined) {
                    mock_ws.onmessage(content.data);
                }
                break;
            case "forward_fail":
                if (mock_ws != undefined) {
                    if(mock_ws.onclose != undefined) {
                        mock_ws.onclose();
                    }
                    mock_ws = undefined;
                }
                break;
            default:
                console.error("Unknown message type", content.type);
        }
    };

    

    ws.onclose = (e) => {
        console.log('Socket is closed. Reconnect will be attempted in 1 second.', e.reason);
        if (mock_ws != undefined) {
            if(mock_ws.onclose != undefined) {
                mock_ws.onclose()
            }
        }
        hide_ui();
        poll_task_run = false;
        reject("Socket closed");
    };

    ws.onerror = (err) => {
        console.error('Socket encountered error: ', err.message, 'Closing socket');
        ws.close();
    };
}

let main = async () => {
    //alert("V2");

    hide_ui();

    //Bind header
    document.getElementById("main_hdr_shutdown").onclick = () => {
        if (confirm("Are you sure to shut down?")) {
            fetch("/shutdown");
        }
    };

    document.getElementById("photo_upload").onchange = async () => {
        let formData = new FormData();           
        formData.append("file", document.getElementById("photo_upload").files[0]);
        let res = await fetch('/upload', {
            method: "POST", 
            body: formData
        });
        let data = await(res.text());
        console.log(data);

        const iframe = document.getElementById('file_upload_frame');
        const iframeDocument = iframe.contentDocument || iframe.contentWindow.document;
        iframeDocument.open();
        iframeDocument.write(data);
        iframeDocument.close();

        document.getElementById('file_upload_frame').innerHTML = res;
        document.getElementById('file_upload_frame').style.display = "initial";
        await new Promise((resolve, reject) => setTimeout(resolve, 2000));
        document.getElementById('file_upload_frame').style.display = "none";
    }

    //GPS
    if (navigator.geolocation) {
        let geo_options = {
            enableHighAccuracy: true,
            timeout: 10,
            maximumAge: 0
        };
        navigator.geolocation.watchPosition((position) => {
            global_gps.position = [position.coords.latitude, position.coords.longitude];
            global_gps.timestamp = Date.now();
            global_gps.accuracy = position.coords.accuracy;
            if (global_gps.listener != undefined) {
                global_gps.listener(global_gps.position);
            }
        }, null, geo_options);
    }

    setInterval(() => {
        document.getElementById("main_hdr_gps").innerText = `${format_gps(global_gps.position)} (${Math.floor((Date.now() - global_gps.timestamp) / 1000)}s, ${(global_gps.accuracy == undefined ? "??" : global_gps.accuracy.toFixed(0))}m)`;
    }, 500);

    //Poll websocket for main UI
    let run_fetches = async () => {
        while (true) {
            console.log("Starting websocket");
            try {
                await new Promise(connect_main);
            } catch {
                console.log("Websocket died");
            }
            await new Promise((resolve, reject) => setTimeout(resolve, 1000));
        };
    };

    run_fetches();
};

window.onload = () => {
    main();
}
