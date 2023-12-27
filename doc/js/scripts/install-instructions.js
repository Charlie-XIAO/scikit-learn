/** This is the script for install.rst. It is partially vendored from the pytorch
  * "Get Started" page: https://pytorch.org/get-started/locally/ */

var supportedOperatingSystems = new Map([
    ["linux", "linux"],
    ["mac", "macos"],
    ["win", "windows"],
]);

/* Determine the default selection of OS */

function getPlatformOS() {
    var platform = navigator.platform.toLowerCase();
    for (var [navPlatformSubstring, os] of supportedOperatingSystems.entries()) {
        if (platform.indexOf(navPlatformSubstring) !== -1) {
            return os;
        }
    }
    return supportedOperatingSystems.values().next().value;  // just return something
}

function getDefaultSelectedOS() {
    var anchor = location.hash;
    var ANCHOR_REGEX = /^#[^ ]+$/;

    // Look for anchor in the href
    if (!ANCHOR_REGEX.test(anchor)) {
        return getPlatformOS();
    }

    // Look for anchor with OS in the first portion
    var testOS = anchor.slice(1).split("-")[0];
    for (var [navPlatformSubstring, os] of supportedOperatingSystems.entries()) {
        if (testOS.indexOf(navPlatformSubstring) !== -1) {
            return os;
        }
    }
    return getPlatformOS();
}

var selectedOptions = {
    os: getDefaultSelectedOS(),
    packager: "pip",
    virtualenv: "venv",
}

var osOptions = document.querySelectorAll("#osRow .option");
var packagerOptions = document.querySelectorAll("#packagerRow .option");
var virtualenvOptions = document.querySelectorAll("#virtualenvRow .option");

/* Update the install instructions based on the selected options */

var instructionBlock = document.getElementById("skInstallInstructions");

var pipMapping = {
    "windows": "pip",
    "macos": "pip",
    "linux": "pip3",
}
var pythonMapping = {
    "windows": "python",
    "macos": "python",
    "linux": "python3",
}

function getOpeningInstruction(os, packager) {
    switch (packager) {
        case "pip":
            switch (os) {
                case "windows":
                    return `Install the 64-bit version of Python 3, for instance from <a href="https://www.python.org/">https://www.python.org</a>.`;
                case "macos":
                    return `Install Python 3 using <a href="https://brew.sh/">homebrew</a> (<code>brew install python</code>) or by manually installing the package from <a href="https://www.python.org">https://www.python.org</a>.`;
                case "linux":
                    return `Install python3 and python3-pip using the package manager of the Linux Distribution.`;
                default:
                    return "";
            }
        case "conda":
            return`Install conda using the <a href="https://docs.conda.io/projects/conda/en/latest/user-guide/install/">Anaconda or miniconda</a> installers or the <a href="https://github.com/conda-forge/miniforge#miniforge">miniforge</a> installers (no administrator permission required for any of those).`;
        default:
            return "";
    }
}

function getVenvActivationInstruction(os) {
    switch (os) {
        case "windows":
            return `sklearn-env\\Scripts\\activate`;
        case "macos":
            return `source sklearn-env/bin/activate`;
        case "linux":
            return `source sklearn-env/bin/activate`;
        default:
            return "";
    }
}

function getCheckInstallInstruction(os, packager) {
    switch (packager) {
        case "pip":
            return [
                `${pythonMapping[os]} -m pip show scikit-learn  # to see which version and where scikit-learn is installed`,
                `${pythonMapping[os]} -m pip freeze  # to see all packages installed in the active virtualenv`,
                `${pythonMapping[os]} -c "import sklearn; sklearn.show_versions()"  # to see the versions of scikit-learn and its dependencies`,
            ];
        case "conda":
            return [
                `conda list scikit-learn  # to see which scikit-learn version is installed`,
                `conda list  # to see all packages installed in the active conda environment`,
                `python -c "import sklearn; sklearn.show_versions()"  # to see the versions of scikit-learn and its dependencies`,
            ];
        default:
            return [];
    }
}

function updateInstructions() {
    var curOs = selectedOptions["os"];
    var curPackager = selectedOptions["packager"];
    var curVirtualenv = selectedOptions["virtualenv"];
    var instruction = "";

    // The opening paragraph
    instruction += `<p>${getOpeningInstruction(curOs, curPackager)} Then run:</p>\n`;

    // The code block for installation
    instruction += `<div class="highlight-default "><div class="highlight"><pre class="sk-install-prompt">`;
    if (curVirtualenv === "venv") {
        instruction += `<span>${pythonMapping[curOs]} -m venv sklearn-env</span>\n`;
        instruction += `<span>${getVenvActivationInstruction(curOs)}</span>\n`;
    }
    instruction += `<span>${pipMapping[curOs]} install -U scikit-learn</span>`;
    instruction += `</pre></div></div>`;

    // The code block for checking installation
    instruction += `<p>In order to check your installation you can use</p>`;
    instruction += `<div class="highlight-default"><div class="highlight"><pre class="sk-install-prompt">`;
    var checkInstallInstrunction = getCheckInstallInstruction(curOs, curPackager);
    for (var i = 0; i < checkInstallInstrunction.length; i++) {
        instruction += `<span>${checkInstallInstrunction[i]}</span>`;
        if (i < checkInstallInstrunction.length - 1) {
            instruction += "\n";
        }
    }
    instruction += `</pre></div></div>`;
    instructionBlock.innerHTML = instruction;
    instructionBlock.setAttribute("data-os", curOs);

    addCopyButtonToCodeCells();  // See copybutton.js from sphinx-copybutton
}

/* Initialize the options and their click handlers */

function initOptions(options, category) {
    options.forEach(function (option) {
        option.addEventListener("click", function () {
            selectedOption(options, this, category);
        });
        if (option.id === selectedOptions[category]) {
            option.classList.add("selected");
        }
    });
}

function selectedOption(options, selection, category) {
    options.forEach(function (option) {
        if (option === selection) {
            option.classList.add("selected");
        } else {
            option.classList.remove("selected");
        }
    });
    selectedOptions[category] = selection.id;
    updateInstructions();
}

initOptions(osOptions, "os");
initOptions(packagerOptions, "packager");
initOptions(virtualenvOptions, "virtualenv");
updateInstructions();
