class ImageUploader {
    constructor(containerId, formFieldId) {
        this.container = document.getElementById(containerId);
        this.formField = formFieldId; //! Django form field id 
        this.uploadedFiles = new Set();
        this.fileInput = document.getElementById(formFieldId);
        this.init();
    }

    //! This function is used to when the image uploader is initialized
    init() {
        const uploadArea = this.container.querySelector(".upload-draggable")
        const previewContainer = document.createElement("div");
        previewContainer.id = "image-preview-container"
        previewContainer.className = "grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-2 xl:grid-cols-3 gap-4 mt-4";
        //? takes in the div to be add which is previewContainer and add it to the parent node of uploadArea (Meaning just after the uploadArea)
        uploadArea.parentNode.insertBefore(previewContainer, uploadArea.nextSibling);
        this.attachEventListeners();
    }


    attachEventListeners() {
        const uploadInput = document.getElementById(this.formField)
        const previewContainer = this.container.querySelector("#image-preview-container")
        uploadInput.addEventListener("change", (e) => {
            const files = e.target.files;
            for (let file of files) {
                if (file.type.startsWith("image/")) {
                    console.log("Console.log 1")
                    console.log(file)
                    this.handleFileUpload(file, previewContainer)
                }
            }
        })



        //! Add drag and drop functionality
        // Add drag and drop support to existing upload area
        const dropZone = this.container.querySelector('.upload-draggable');

        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('border-primary-600');
        });

        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('border-primary-600');
        });

        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('border-primary-600');

            const files = e.dataTransfer.files;
            for (let file of files) {
                if (file.type.startsWith('image/')) {
                    this.handleFileUpload(file, previewContainer);
                }
            }
        });

    }


    handleFileUpload(file, previewContainer) {

        const reader = new FileReader();
        reader.onload = (e) => {
            const preview = this.createImagePreview(e.target.result)

            //? Add Remove funtionality
            preview.querySelector(".remove-image").addEventListener("click", () => {
                preview.remove();
                this.uploadedFiles.delete(file)
                this.updateFormInput()

                // clear  input if no files remain
                if (this.uploadedFiles.size === 0) {
                    document.getElementById(this.formField).value = "";
                }
            })

            // Add preview functionality
            preview.querySelector(".preview-image").addEventListener("click", () => {
                // window.open(e.target.src, "_blank")
                this.showImagePreview(e.target.result);
            })

            //? handle the file upload
            previewContainer.appendChild(preview)
            this.uploadedFiles.add(file)
            this.updateFormInput()
        };
        reader.readAsDataURL(file);
    }

    createImagePreview(imageUrl) {
        const preview = document.createElement("div")
        preview.className = 'group relative rounded border p-2 flex';
        preview.innerHTML = `
            <img src="${imageUrl}" class="rounded max-h-[140px] max-w-full" alt="preview">
            <div class="absolute inset-2 bg-gray-900/[.7] group-hover:flex hidden text-xl items-center justify-center">
                <span class="text-gray-100 hover:text-gray-300 cursor-pointer p-1.5 preview-image">
                    <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 20 20" aria-hidden="true" height="1em" width="1em" xmlns="http://www.w3.org/2000/svg">
                        <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"></path>
                        <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"></path>
                    </svg>
                </span>
                <span class="text-gray-100 hover:text-gray-300 cursor-pointer p-1.5 remove-image">
                    <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 20 20" aria-hidden="true" height="1em" width="1em" xmlns="http://www.w3.org/2000/svg">
                        <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"></path>
                    </svg>
                </span>
            </div>
            `;

        return preview;

    }

    showImagePreview(imageUrl) {
        const modal = document.createElement('div')
        modal.className = 'fixed inset-0 bg-black  bg-opacity-50 flex items-center justify-center z-50 bg-gray-900/[.7]';
        modal.innerHTML = `
            <div class="relative">
                <img src="${imageUrl}" class="max-h-[90vh] max-w-[90vw]" alt="preview">
                <button class="absolute top-4 right-4 text-white text-xl">&times;</button>
            </div>
            `;
        modal.addEventListener("click", () => {
            modal.remove()
        })
        document.body.appendChild(modal)

    }

    updateFormInput() {
        // Create a DataTransfer object to create a new FileList
        const dataTransfer = new DataTransfer();
        // Add all files from uploadedFiles to the DataTransfer object

        this.uploadedFiles.forEach(file => {
            console.log("Data transfer runining")
            dataTransfer.items.add(file)
        })

        // Update the form input with the new FileList
        this.fileInput.files = dataTransfer.files;
        console.log(this.fileInput.files)
    }
}