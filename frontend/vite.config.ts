import path from "path"
import { fileURLToPath } from "url"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            "@": path.resolve(__dirname, "src"),
        },
    },
    build: {
        rollupOptions: {
            output: {
                manualChunks: {
                    "vendor-react": ["react", "react-dom", "react-router-dom"],
                    "vendor-utils": ["lucide-react", "framer-motion", "clsx", "tailwind-merge"],
                    "vendor-ui": [
                        "@radix-ui/react-avatar",
                        "@radix-ui/react-dialog",
                        "@radix-ui/react-dropdown-menu",
                        "@radix-ui/react-label",
                        "@radix-ui/react-popover",
                        "@radix-ui/react-scroll-area",
                        "@radix-ui/react-select",
                        "@radix-ui/react-separator",
                        "@radix-ui/react-slider",
                        "@radix-ui/react-slot",
                        "@radix-ui/react-switch",
                        "@radix-ui/react-tabs",
                        "@radix-ui/react-tooltip"
                    ],
                    "vendor-viz": ["recharts"],
                }
            }
        }
    }
})
