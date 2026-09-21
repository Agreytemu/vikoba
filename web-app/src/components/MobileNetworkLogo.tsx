import { FC } from "react";

import mpesaLogo from "@/assets/mpesa logo.jpg";
import airtelLogo from "@/assets/airtel.jpg";
import halopesaLogo from "@/assets/halopesalogo.jpg";
import mixxLogo from "@/assets/mixxbyyaslogo.jpg";

/**
 * Brand marks for the Snippe mobile-money networks, rendered straight from the
 * real logo images shipped in src/assets (M-Pesa, Airtel, Halopesa and Mixx by
 * Yas). Height is fixed to `size`; width follows the image's natural aspect
 * ratio so wide wordmarks (Airtel) keep their proportions instead of being
 * squeezed into a square.
 */
const BRAND_IMAGES: Record<string, string> = {
  mpesa: mpesaLogo,
  airtel: airtelLogo,
  mixx: mixxLogo,
  halotel: halopesaLogo,
};

const BRAND_LABELS: Record<string, string> = {
  mpesa: "M-Pesa",
  airtel: "Airtel Money",
  mixx: "Mixx by Yas",
  halotel: "Halopesa",
};

const MobileNetworkLogo: FC<{ networkId?: string; size?: number; className?: string }> = ({
  networkId,
  size = 40,
  className = "",
}) => {
  if (!networkId) return null;
  const src = BRAND_IMAGES[networkId];
  if (!src) return null;
  return (
    <img
      src={src}
      alt={BRAND_LABELS[networkId] ?? networkId}
      style={{ height: size, width: "auto" }}
      className={className}
    />
  );
};

export default MobileNetworkLogo;