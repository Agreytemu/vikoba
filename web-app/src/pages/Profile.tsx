import React, { useEffect, useRef, useState } from "react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
// constants
import { toast } from "react-toastify";
import { resolveMediaUrl } from "@/constants";
import { useGetUserProfile, useUpdateUserProfile } from "@/hooks/api/profile";
import { getApiErrorMessage } from "@/lib/utils";
// components
import Button from "@/components/Button";
import Spinner from "@/components/Spinner";
import LucideIcon from "@/components/LucideIcon";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";

import ProfilePlaceholder from "@/assets/profile-placeholder.png";
import { useUserProfileInfo } from "@/hooks/useUserProfile";
import VerificationWorkflow from "@/components/member/VerificationWorkflow";
const formSchema = z.object({
  username: z
    .string()
    .min(2, { message: "Username must be at least 2 characters long" }),
  email: z.string().email({ message: "Invalid email address" }),
  role_display: z.string().optional(),
  profile_image: z
    .any()
    .optional()
    .refine(
      (file) => !file || !(file instanceof File) || file.size < 7 * 1024 * 1024,
      { message: "Image must be less than 7MB." },
    ),
});

const Profile = () => {
  const { profile: authProfile } = useUserProfileInfo();
  const isMember = authProfile?.role === "ME";
  const { data: profile, isLoading, error } = useGetUserProfile();
  const { mutateAsync: updateProfile, isPending: isUpdatingProfile } =
    useUpdateUserProfile();

  const [preview, setPreview] = useState("");

  const imageInputRef = useRef<HTMLInputElement | null>(null);

  const handleImageUpdate = () => {
    imageInputRef.current?.click();
  };

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      username: "",
      email: "",
      role_display: "",
      profile_image: undefined,
    },
  });

  useEffect(() => {
    if (!profile) {
      return;
    }

    form.reset({
      username: profile.username ?? "",
      email: profile.email ?? "",
      role_display: profile.profile?.role_display ?? profile.role ?? "",
      profile_image: undefined,
    });
  }, [profile, form]);

  const handleImageUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    if (file.size > 7 * 1024 * 1024) {
      toast.error("Image is too large — must be less than 7MB. Please choose a smaller image.", { autoClose: 3000 });
      event.target.value = "";
      return;
    }
    const imageUrl = URL.createObjectURL(file);
    setPreview(imageUrl);
    form.setValue("profile_image", file, { shouldValidate: true });
  };

  const onSubmit = async (values: z.infer<typeof formSchema>) => {
    try {
      await updateProfile({
        username: values.username,
        email: values.email,
        profile_image:
          values.profile_image instanceof File ? values.profile_image : undefined,
      });
      toast.success("Profile updated.", { autoClose: 2000 });
      setPreview("");
    } catch (error: unknown) {
      toast.error(getApiErrorMessage(error as Error, "Could not update profile"), { autoClose: 3000 });
    }
  };

  const currentProfileImage =
    typeof profile?.profile?.profile_image === "string"
      ? profile.profile.profile_image
      : typeof profile?.profile_image === "string"
        ? profile.profile_image
        : "";

  const resolvedProfileImage = currentProfileImage
    ? resolveMediaUrl(currentProfileImage)
    : ProfilePlaceholder;

  if (isLoading) {
    return (
      <div className="w-full min-h-screen flex justify-center items-center">
        <Spinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full min-h-screen flex justify-center items-center">
        Unable to load profile.
      </div>
    );
  }

  return (
    <div className="w-2/3 mx-auto mt-5">
      <h1 className="text-2xl mb-4 text-center">Update Profile</h1>
      <div className=" w-full flex justify-center items-center   dark:border-slate-400 rounded-md">
        <Form {...form}>
          <form
            className=" space-y-4 mb-5"
            onSubmit={form.handleSubmit(onSubmit)}
          >
            <div className="relative ">
              <img
                src={preview ? preview : resolvedProfileImage}
                alt="profile image"
                className=" w-48 h-48 rounded-full mx-auto object-fill"
              />
              <LucideIcon
                name="Camera"
                className="absolute bottom-4 right-12"
                onClick={handleImageUpdate}
              />
            </div>
            <FormField
              control={form.control}
              name="profile_image"
              render={() => (
                <FormItem>
                  <FormLabel>Profile Image:</FormLabel>
                  <FormControl>
                    <Input
                      placeholder=""
                      accept="image/*"
                      type="file"
                      onChange={handleImageUpload}
                      ref={imageInputRef}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="username"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>User Name:</FormLabel>
                  <FormControl>
                    <Input
                      placeholder=""
                      {...field}
                      className="!focus-visible:ring-0 !focus-visible:ring-offset-0"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email:</FormLabel>
                  <FormControl>
                    <Input
                      placeholder=""
                      {...field}
                      className="!focus-visible:ring-0 !focus-visible:ring-offset-0"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="role_display"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Role:</FormLabel>
                  <FormControl>
                    <Input
                      placeholder=""
                      {...field}
                      disabled
                      className="!focus-visible:ring-0 !focus-visible:ring-offset-0 cursor-not-allowed"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button
              type="submit"
              text={isUpdatingProfile ? <Spinner /> : "Update Profile"}
              className="w-full mb-8"
            />
          </form>
        </Form>
      </div>
      {isMember && (
        <div className="mt-10 space-y-6">
          <h2 className="text-xl font-semibold text-center">Verification steps</h2>
          <VerificationWorkflow />
        </div>
      )}
    </div>
  );
};

export default Profile;
