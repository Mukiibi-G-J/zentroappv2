import React from "react";
import {
  Br,
  Cut,
  Image,
  Line,
  Printer,
  Row,
  Text,
  render,
  type CharacterSet,
  type TextSize,
} from "react-thermal-printer";
import type { ReceiptDocument, ReceiptDocumentNode } from "./types";

function toTextSize(value: number): TextSize {
  return Math.min(8, Math.max(1, Math.round(value))) as TextSize;
}

function resolveTextSize(style: {
  double?: boolean;
  size?: number;
}): { width: TextSize; height: TextSize } | undefined {
  if (style.double) {
    return { width: 2, height: 2 };
  }
  if (style.size) {
    const size = toTextSize(style.size);
    return { width: size, height: size };
  }
  return undefined;
}

export interface ThermalCompileConfig {
  type?: "epson" | "star";
  width?: number;
  characterSet?: CharacterSet;
}

function nodeToJsx(node: ReceiptDocumentNode, key: number): React.ReactNode {
  const style = node.style || {};
  switch (node.type) {
    case "image":
      if (!node.src) return null;
      return <Image key={key} src={node.src} align={style.align || "center"} />;
    case "text":
      return (
        <Text
          key={key}
          align={style.align}
          bold={style.bold}
          size={resolveTextSize(style)}
        >
          {node.text || ""}
        </Text>
      );
    case "row":
      return (
        <Row
          key={key}
          left={
            <Text bold={style.bold}>{node.left || ""}</Text>
          }
          right={
            <Text bold={style.bold}>{node.right || ""}</Text>
          }
          gap={2}
        />
      );
    case "rule":
      return <Line key={key} />;
    case "feed":
      return (
        <React.Fragment key={key}>
          {Array.from({ length: node.lines || 1 }).map((_, i) => (
            <Br key={i} />
          ))}
        </React.Fragment>
      );
    case "cut":
      return <Cut key={key} />;
    default:
      return null;
  }
}

export function compileDocumentToThermalTree(
  document: ReceiptDocument,
  config: ThermalCompileConfig = {},
): React.ReactElement<React.ComponentProps<typeof Printer>> {
  const {
    type = "epson",
    width = document.paperProfile?.charsPerLine ?? 42,
    characterSet,
  } = config;

  return (
    <Printer type={type} width={width} characterSet={characterSet}>
      {document.nodes.map((node, i) => nodeToJsx(node, i))}
    </Printer>
  );
}

export async function compileDocumentToEscPos(
  document: ReceiptDocument,
  config: ThermalCompileConfig = {},
): Promise<Uint8Array> {
  const tree = compileDocumentToThermalTree(document, config);
  return await render(tree);
}
