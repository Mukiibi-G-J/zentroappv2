// document.addEventListener("htmx:afterRequest", (evt) => {
//     const response = JSON.parse(evt.detail.xhr.responseText)
//     const downloadBtn = document.getElementById("downloadBtn")
//     const downloadText = document.getElementById("downloadText")


//     if (response.template) {
//         downloadBtn.href = response.template
//         downloadText.textContent = `Click to download '${response.model_name.toString().toUpperCase()}' Template`
//         downloadBtn.classList.remove("btn-disabled")
//         downloadBtn.removeAttribute("disabled")

//     } else {
//         downloadBtn.href = "#"  
//         downloadBtn.classList.add("btn-disabled")
//         downloadBtn.setAttribute("disabled", "")
//         downloadText.textContent = "Select a template to download"
//     }
// })
// const fileInput = document.getElementById("fileInput");
// const fileInfo = document.getElementById("fileInfo");
// const fileName = fileInfo.querySelector(".file-name");
// const fileSize = fileInfo.querySelector(".file-size");
// const processButton = document.getElementById("processButton");

// fileInput.addEventListener("change", function (e) {
//   const file = e.target.files[0];
//   if (file) {
//     fileName.textContent = file.name;
//     fileSize.textContent = formatFileSize(file.size);
//     fileInfo.classList.remove("hidden");
//     processButton.classList.remove("hidden");
//   }
// });

// function removeFile() {
//   fileInput.value = "";
//   fileInfo.classList.add("hidden");
//   processButton.classList.add("hidden");
// }
// function formatFileSize(bytes) {
//   if (bytes === 0) return "0 Bytes";
//   const k = 1024;
//   const sizes = ["Bytes", "KB", "MB", "GB"];
//   const i = Math.floor(Math.log(bytes) / Math.log(k));
//   return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
// }

class FileUploadHandler {
    constructor() {
        this.fileInput = document.getElementById("fileInput");
        this.fileInfo = document.getElementById("fileInfo");
        this.fileName = this.fileInfo.querySelector(".file-name");
        this.fileSize = this.fileInfo.querySelector(".file-size");
        this.processButton = document.getElementById("processButton");
        this.downloadBtn = document.getElementById("downloadBtn");
        this.downloadText = document.getElementById("downloadText");
        this.removeFileBtn = document.getElementById("removeFileBtn");
        this.dialogContainer = document.getElementById("dialogContainer");
        this.uploadModalResults = document.querySelector(".upload-modal-container");
        this.uploadModalResultsClose = document.getElementById("uploadModalResultsClose");
        this.statusCheckInterval = null;

        this.initializeEventListeners();
    }

    initializeEventListeners() {
        // File input change handler
        this.fileInput?.addEventListener("change", (e) => this.handleFileChange(e));

        // HTMX after request handler
        document.addEventListener("htmx:afterRequest", (evt) => {
            if (evt.detail.requestConfig.elt.id === "uploadForm") {
                // this.handleProcessing();

            } else {
                this.handleTemplateResponse(evt);

            }
        });

        //
        document.addEventListener("htmx:afterSwap", (evt) => {
            this.handleProcessing(evt);
        })

        this.removeFileBtn.addEventListener("click", () => this.removeFile());

        // this.processButton?.addEventListener("click", () => this.handleProcessButtonClick());
        this.dialogContainer?.addEventListener("click", (e) => this.handleModalInteractions(e));
        this.uploadModalResultsClose?.addEventListener("click", () => this.closeModal());


        // Add click handler for backdrop
        document.addEventListener("click", (e) => {
            if (e.target.matches(".upload-modal-backdrop")) {
                this.closeModal();
            }
        });

        // Optionally add ESC key handler
        document.addEventListener("keydown", (e) => {
            if (e.key === "Escape" && this.uploadModalResults) {
                this.closeModal();
            }
        });
    }

    handleFileChange(e) {
        const file = e.target.files[0];
        if (file) {
            this.fileName.textContent = file.name;
            this.fileSize.textContent = this.formatFileSize(file.size);
            this.fileInfo.classList.remove("hidden");
            this.processButton.classList.remove("hidden");
        }
    }

    handleTemplateResponse(evt) {
        try {
            console.log(evt)
            console.log(evt.detail.xhr.responseText);
            if (!evt.detail.xhr.responseText) {
                alert("No response from server");
                return;
            }
            const response = JSON.parse(evt.detail.xhr.responseText);
            console.log(response);
            if (response.template) {
                this.updateDownloadButton(
                    response.template,
                    `Click to download '${response.model_name.toString().toUpperCase()}' Template`,
                    false
                );
            } else {
                this.updateDownloadButton(
                    "#",
                    "Select a template to download",
                    true
                );
            }
        } catch (error) {
            console.error("Error processing template response:", error);
        }
    }

    updateDownloadButton(href, text, disabled) {
        this.downloadBtn.href = href;
        this.downloadText.textContent = text;

        if (disabled) {
            this.downloadBtn.classList.add("btn-disabled");
            this.downloadBtn.setAttribute("disabled", "");
        } else {
            this.downloadBtn.classList.remove("btn-disabled");
            this.downloadBtn.removeAttribute("disabled");
        }
    }

    closeModal() {
        const modalContainer = document.querySelector(".upload-modal-container");
        if (modalContainer) {
            modalContainer.remove();
            // Re-enable scrolling on the body
            document.body.style.overflow = "auto";
        }
        const closeButton = dialogContainer.querySelector('[data-modal-close]');
        if (closeButton) {
            closeButton.addEventListener('click', () => {
                const modal = closeButton.closest('.upload-modal-backdrop');
                if (modal) {
                    modal.remove();
                }
            });
        }
    }

    removeFile() {
        this.fileInput.value = "";
        this.fileInfo.classList.add("hidden");
        this.processButton.classList.add("hidden");
    }


    formatFileSize(bytes) {
        if (bytes === 0) return "0 Bytes";
        const k = 1024;
        const sizes = ["Bytes", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    }

    handleProcessing(evt) {
        console.log(evt.detail.target.id);
        if (evt.detail.target.id === "dialogContainer") {
            const processingState = document.getElementById("processingState");
            const progressBar = document.getElementById("progressBar");
            const statusMessage = document.getElementById("statusMessage");
            // Add null check before accessing dataset
            if (
                processingState &&
                processingState.dataset &&
                processingState.dataset.processId
            ) {
                const processId = processingState.dataset.processId;
                console.log(processId);
                // this.checkStatus(processId);
                this.statusCheckInterval = setInterval(() => {
                    this.checkStatus(processId)
                        .then(data => {
                            console.log(progressBar)
                            console.log(statusMessage)
                            progressBar.style.width = `${data.progress}%`;
                            statusMessage.textContent = data.message;
                            if (data.status === "completed") {
                                console.log("completed");
                                this.showCompletionModal(data);
                            }
                            if (data.status === "failed") {
                                console.log("failed");
                                this.showCompletionModal(data);
                            }
                        })
                }, 2000);
            }
        }
    }

    checkStatus(processId) {
        return new Promise((resolve, reject) => {
            fetch(`/process-upload-status/${processId}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.json();
                })
                .then(data => {
                    console.log("Status data:", data);
                    resolve(data);
                })
                .catch(error => {
                    console.error("Fetch error:", error);
                    reject(error);
                });
        });
    }
    showCompletionModal(data) {
        const dialogContainer = document.getElementById("dialogContainer");
        const isSuccess = data.status === "completed";
        console.log(isSuccess)
        // if (isSuccess) {
        this.cleanup();
        dialogContainer.innerHTML = `
    <div class="upload-modal-backdrop flex items-center justify-center">
        <div class="upload-modal-container">
            <div class="upload-modal-content card w-[450px]">
                <!-- Card Header with Close Button -->
                <div class="card-header flex justify-between items-center p-4 border-b border-gray-200 dark:border-gray-600">
                    <h5 class="font-semibold">File Processing</h5>
                    <span
                        class="text-gray-400 hover:text-gray-600 cursor-pointer"
                        id="uploadModalResultsClose"
                        data-modal-close
                    >
                        <svg
                            stroke="currentColor"
                            fill="currentColor"
                            stroke-width="0"
                            viewBox="0 0 20 20"
                            aria-hidden="true"
                            height="1em"
                            width="1em"
                            xmlns="http://www.w3.org/2000/svg"
                        >
                            <path
                                fill-rule="evenodd"
                                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                                clip-rule="evenodd"
                            ></path>
                        </svg>
                    </span>
                </div>

                <div class="card-body p-6">
                    <div class="flex flex-col items-center">
                        <!-- Status Icon -->
                        <div class="mb-6">
                            ${isSuccess ? `
                                <span class="avatar avatar-circle" style="width: 80px; height: 80px; background-color: rgb(220 252 231); color: rgb(22 163 74);">
                                    <span class="avatar-icon avatar-icon-lg">
                                        <svg 
                                            xmlns="http://www.w3.org/2000/svg" 
                                            fill="none" viewBox="0 0 24 24" 
                                            stroke-width="1.5" stroke="currentColor" 
                                            aria-hidden="true" 
                                            class="w-18 h-18" 
                                            style="width: 60px; height: 60px; color: green;"
                                        >
                                            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                                        </svg>
                                    </span>
                                </span>
                            ` : `
                                <span class="avatar avatar-circle" style="width: 80px; height: 80px; background-color: rgb(254 226 226); color: rgb(220 38 38);">
                                     <span class="avatar-icon avatar-icon-lg">
                                            <svg
                                                xmlns="http://www.w3.org/2000/svg"
                                                fill="none"
                                                viewBox="0 0 24 24"
                                                stroke-width="1.5"
                                                stroke="currentColor"
                                                aria-hidden="true"
                                                class="w-18 h-18"
                                                style="width: 60px; height: 60px; color: black;"
                                            >
                                                <path
                                                stroke-linecap="round"
                                                stroke-linejoin="round"
                                                d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                                                ></path>
                                            </svg>
                                        </span>
                                </span>
                            `}
                        </div>

                        <!-- Title and Message -->
                        <div class="text-center mb-4">
                            <h6 class="font-semibold text-gray-900 dark:text-gray-100">
                                ${isSuccess ? 'Processing Complete' : 'Processing Failed'}
                            </h6>
                            <p class="text-sm text-gray-600 dark:text-gray-400 mt-1">
                                ${data.message}
                            </p>
                        </div>
                        
                        <!-- Content Section -->
                        ${isSuccess && data.summary ? `
                            <div class="w-full mt-4">
                                <div class="grid grid-cols-2 gap-4 mb-4">
                                    <div class="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg text-center">
                                        <p class="text-sm text-gray-600 dark:text-gray-400">Total Records</p>
                                        <p class="font-semibold text-xl">${data.summary.total_records || 0}</p>
                                    </div>
                                    <div class="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg text-center">
                                        <p class="text-sm text-gray-600 dark:text-gray-400">Created Records</p>
                                        <p class="font-semibold text-xl">${data.summary.created_records || 0}</p>
                                    </div>
                                </div>
                                <div class="grid grid-cols-2 gap-4">
                                    <div class="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg text-center">
                                        <p class="text-sm text-gray-600 dark:text-gray-400">Updated Records</p>
                                        <p class="font-semibold text-xl">${data.summary.updated_records || 0}</p>
                                    </div>
                                    <div class="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg text-center">
                                        <p class="text-sm text-gray-600 dark:text-gray-400">Failed Records</p>
                                        <p class="font-semibold text-xl text-red-500">${data.summary.failed_records || 0}</p>
                                    </div>
                                </div>
                                ${data.details && data.details.length > 0 ? `
                                    <div class="mt-4">
                                        <div class="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg">
                                            <p class="text-sm text-gray-600 dark:text-gray-400 mb-2">Processing Details</p>
                                            <div class="max-h-40 overflow-y-auto">
                                                ${data.summary.details.map(detail => `
                                                    <div class="flex items-center justify-between py-1 text-sm">
                                                        <span>${detail.type}: ${detail.name}</span>
                                                        <span class="capitalize ${detail.status === 'created' ? 'text-green-500' :
                detail.status === 'updated' ? 'text-blue-500' :
                    'text-red-500'
            }">${detail.status}</span>
                                                    </div>
                                                `).join('')}
                                            </div>
                                        </div>
                                    </div>
                                ` : ''}
                            </div>
                        ` : ''}
                        
                        ${!isSuccess && data.error ? `
                            <div class="w-full mt-4">
                                <div class="bg-red-50 border border-red-200 dark:bg-red-900/20 dark:border-red-800/20 p-4 rounded-lg">
                                    <div class="flex items-start">
                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" aria-hidden="true" class="w-6 h-6 text-red-500 mt-0.5 mr-2">
                                            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"></path>
                                        </svg>
                                        <div>
                                            <h6 class="font-medium text-red-600 dark:text-red-400">Error Details</h6>
                                            <p class="text-sm text-red-600 dark:text-red-400 mt-1">
                                                ${data.error}
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ` : ''}
                    </div>
                </div>

                <div class="card-footer bg-gray-50 dark:bg-gray-700 px-3 py-3">
                    <div class="flex justify-end gap-2">
                        <button 
                            type="button"
                            class="btn btn-default"
                            data-modal-close
                        >
                            Close
                        </button>
                        ${isSuccess ? `
                            <a 
                                href="${data.summary.url}" 
                                class="btn bg-sky-500 hover:bg-sky-400 active:bg-sky-600 text-white"
                            >
                                <span class="flex items-center">
                                    <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                                    </svg>
                                    View Items
                                </span>
                            </a>
                        ` : `
                            <button 
                                type="button"
                                class="btn bg-sky-500 hover:bg-sky-400 active:bg-sky-600 text-white"
                                onclick="window.location.reload()"
                            >
                                <span class="flex items-center">
                                    <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                                    </svg>
                                    Try Again
                                </span>
                            </button>
                        `}
                    </div>
                </div>
            </div>
        </div>
    </div>`;

        // Add event listeners for closing
        const closeButtons = dialogContainer.querySelectorAll('[data-modal-close]');
        closeButtons.forEach(button => {
            button.addEventListener('click', () => {
                // Remove all modal-related elements
                dialogContainer.querySelectorAll('.upload-modal-backdrop, .fixed').forEach(el => el.remove());
                // Clear the dialog container
                dialogContainer.innerHTML = '';
            });
        });
    }

    // console.log(dialogContainer);
    // }


    // handleProcessButtonClick() {
    //     console.log("Process button clicked");
    //     this.dialogContainer.innerHTML = `
    //         <div class="upload-modal-container">
    //             <div class="upload-modal-content">
    //                 <span class="upload-modal-close" data-modal-close>
    //                     <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 20 20" aria-hidden="true" height="1em" width="1em" xmlns="http://www.w3.org/2000/svg">
    //                         <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
    //                     </svg>
    //                 </span>
    //                 <h5 class="upload-modal-title">Process File</h5>
    //                 <p class="upload-modal-text">Are you sure you want to process this file?</p>
    //                 <div class="upload-modal-actions">
    //                     <button class="btn btn-plain" data-modal-close>Cancel</button>
    //                     <button class="btn btn-solid" data-modal-confirm>Process</button>
    //                 </div>
    //             </div>
    //             <div class="upload-modal-backdrop" data-modal-close></div>
    //         </div>
    //     `;
    //     document.body.style.overflow = 'hidden';
    // }
    // Add cleanup method
    cleanup() {
        const dialogContainer = document.getElementById("dialogContainer");
        if (dialogContainer) {
            clearInterval(this.statusCheckInterval);
            this.statusCheckInterval = null;
            dialogContainer.querySelectorAll('.upload-modal-backdrop, .fixed').forEach(el => el.remove());
            dialogContainer.innerHTML = '';
        }
    }

    handleModalInteractions(e) {
        if (e.target.hasAttribute('data-modal-close') ||
            e.target.closest('[data-modal-close]') ||
            e.target.classList.contains('upload-modal-backdrop')) {
            this.closeModal();
        }

        if (e.target.hasAttribute('data-modal-confirm')) {
            this.processFile();
            this.closeModal();
        }
    }

    processFile() {
        // Add your file processing logic here
        console.log('Processing file...');
    }

    // Add method to show modal if needed
    showModal() {
        if (this.uploadModalResults) {
            this.uploadModalResults.style.display = "flex";
            document.body.style.overflow = "hidden"; // Prevent background scrolling
        }
    }
}

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
    new FileUploadHandler();
});