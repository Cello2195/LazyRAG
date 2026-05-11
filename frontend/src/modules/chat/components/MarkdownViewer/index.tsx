import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import classnames from "classnames";
import "katex/dist/katex.min.css";
import { Popover } from "antd";
import rehypeSanitize from "rehype-sanitize";
import "./markdown.scss";
import "./index.scss";
import { useEffect, useState } from "react";
import { customSchema } from "./config";
import rehypeRaw from "rehype-raw";
import { BASE_URL } from "@/components/request";

function normalizeBrokenArtifactHref(rawHref: string): string {
  const href = (rawHref || "").trim();
  if (!href) return href;

  const isSignedArtifactPath = (path: string): boolean =>
    path.startsWith("/api/chat/artifacts/static-files/") ||
    path.startsWith("/api/core/static-files/") ||
    path.startsWith("/static-files/");

  const buildSignedPath = (rawPath: string, search = "", hash = ""): string => {
    let path = (rawPath || "").trim().replace(/\\/g, "/");
    if (!path) return href;
    path = path.replace(/^\/+/, "");

    const uploadPrefixes = [
      "var/lib/lazyrag/uploads/",
      "lazyrag/uploads/",
      "uploads/",
    ];
    for (const prefix of uploadPrefixes) {
      if (path.startsWith(prefix)) {
        path = path.slice(prefix.length);
        break;
      }
    }

    const marker = "agent-results/";
    const markerIdx = path.indexOf(marker);
    if (markerIdx < 0) return href;
    const rel = path.slice(markerIdx);
    return `/api/chat/artifacts/static-files/${rel}${search}${hash}`;
  };

  if (/^https?:\/\//i.test(href)) {
    try {
      const parsed = new URL(href);
      const pathname = parsed.pathname || "";
      if (isSignedArtifactPath(pathname)) {
        return `${pathname}${parsed.search || ""}${parsed.hash || ""}`;
      }
      if (pathname.includes("/agent-results/")) {
        return buildSignedPath(pathname, parsed.search || "", parsed.hash || "");
      }
      if ((parsed.hostname || "").toLowerCase().startsWith("agent-results")) {
        return buildSignedPath(pathname, parsed.search || "", parsed.hash || "");
      }
      return href;
    } catch {
      return href;
    }
  }

  if (/^agent-results\//i.test(href)) {
    return buildSignedPath(href);
  }

  if (/^(\/)?(var\/lib\/lazyrag\/uploads\/|lazyrag\/uploads\/|uploads\/).*agent-results\//i.test(href)) {
    return buildSignedPath(href);
  }

  return href;
}

function resolveLinkHref(rawHref?: string): string {
  const href = normalizeBrokenArtifactHref((rawHref || "").trim());
  if (!href) return "";
  const isArtifactPath =
    href.startsWith("/api/chat/artifacts/static-files/") ||
    href.startsWith("/api/core/static-files/") ||
    href.startsWith("/static-files/");
  if (isArtifactPath) return href;

  const lower = href.toLowerCase();
  if (
    lower.startsWith("http://") ||
    lower.startsWith("https://") ||
    lower.startsWith("mailto:") ||
    lower.startsWith("tel:") ||
    lower.startsWith("#")
  ) {
    return href;
  }

  const base =
    (BASE_URL || "").trim().replace(/\/+$/, "") ||
    (typeof window !== "undefined" ? window.location.origin : "");
  if (!base) return href;
  if (href.startsWith("/")) return `${base}${href}`;

  return `${base}/${href.replace(/^\/+/, "")}`;
}

const ImageComponent = (props: any) => {
  const [imageLoadError, setImageLoadError] = useState(false);
  if (imageLoadError) {
    return null;
  }

  return (
    <img
      {...props}
      onError={() => setImageLoadError(true)}
      onLoad={() => setImageLoadError(false)}
    />
  );
};

const MarkdownViewer = (props: any) => {
  const { children, className = "", sources = [], IS_STREAMING } = props;

  const [markSources, setMarkSources] = useState<any[]>([]);

  useEffect(() => {
    if (sources && sources.length > 0) {
      setMarkSources(sources);
    }
  }, [sources]);

  return (
    <div
      className={classnames("rag-markdown", {
        [className]: !!className,
      })}
    >
      <Markdown
        {...props}
        remarkPlugins={[[remarkGfm, { singleTilde: false }], remarkMath]}
        rehypePlugins={[
          rehypeRaw,
          rehypeKatex,
          [rehypeSanitize, customSchema],
        ]}
        components={{
          a(props: any) {
            const href = props.href;
            if (href === "#source") {
              if (IS_STREAMING) {
                return (
                  <span
                    className="md-segment-index"
                    style={{ backgroundColor: "var(--color-text-description)" }}
                  >
                    {props.children}
                  </span>
                );
              }
              return (
                <Popover
                  title={props.title || ""}
                  content={
                    <div className="md-content-card">
                      <div className="md-content-card-content">
                        <MarkdownViewer>
                          {
                            markSources.find(
                              (source) => source.index == props.children,
                            )?.content
                          }
                        </MarkdownViewer>
                      </div>
                    </div>
                  }
                >
                  <span className="md-segment-index">{props.children}</span>
                </Popover>
              );
            }

            const rawHref = String(props.href || "");
            const normalizedHref = normalizeBrokenArtifactHref(rawHref);
            const resolvedHref = resolveLinkHref(rawHref);
            let children = props.children;
            if (
              typeof props.children === "string" &&
              props.children.trim() === rawHref &&
              normalizedHref &&
              normalizedHref !== rawHref
            ) {
              children = normalizedHref;
            }
            return (
              <a href={resolvedHref} target="_blank" rel="noopener noreferrer">
                {children}
              </a>
            );
          },
          script() {
            return null;
          },
          li(props: any) {
            const children = Array.isArray(props.children)
              ? props.children.filter((item: any) => item !== "\n")
              : props.children;

            return <li>{children}</li>;
          },
          img: ImageComponent,
          ...props.components,
        }}
      >
        {children || ""}
      </Markdown>
    </div>
  );
};

export default MarkdownViewer;
